import csv
import io
import json
import xml.etree.ElementTree as ET
import zipfile
from collections.abc import Callable, Sequence
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any

from sp_farms.application.account_service import AccountService
from sp_farms.application.secret_service import SecretService
from sp_farms.application.secrets import SecretRepository
from sp_farms.application.unit_of_work import UnitOfWork
from sp_farms.domain.account_exchange import (
    EXPORT_FIELD_LABELS,
    PRESET_FIELDS,
    ConflictStrategy,
    ExportFormat,
    ExportPreset,
    ImportDryRunResult,
    ImportExecutionResult,
    ImportRowResult,
    contains_secret_fields,
)
from sp_farms.domain.account_onboarding import (
    AccountOnboardingRequest,
    OnboardingSource,
    validate_onboarding_request,
)
from sp_farms.domain.accounts import (
    AccountStatus,
)
from sp_farms.domain.secrets import SecretType
from sp_farms.infrastructure.vault import (
    EncryptedSecretArchive,
    decrypt_secret,
    encrypt_secret,
)


class AccountExchangeService:
    def __init__(
        self,
        accounts: AccountService,
        unit_of_work: Callable[[], UnitOfWork] | None = None,
        secrets: SecretService | None = None,
        secret_repository_factory: Callable[[UnitOfWork], SecretRepository] | None = None,
    ) -> None:
        self._accounts = accounts
        self._unit_of_work = unit_of_work
        self._secrets = secrets
        self._secret_repo_factory = secret_repository_factory

    def export_accounts(
        self,
        account_ids: Sequence[str] | None = None,
        export_format: ExportFormat = ExportFormat.CSV,
        preset: ExportPreset = ExportPreset.FULL,
        custom_fields: Sequence[str] | None = None,
    ) -> bytes:
        all_accounts = self._accounts.list_accounts()
        if account_ids:
            target_ids = set(account_ids)
            accounts = [a for a in all_accounts if a.id in target_ids]
        else:
            accounts = list(all_accounts)

        field_keys = custom_fields or PRESET_FIELDS.get(preset, PRESET_FIELDS[ExportPreset.FULL])
        categories = {c.id: c.name for c in self._accounts.list_categories()}
        tags = {t.id: t.name for t in self._accounts.list_tags()}

        records: list[dict[str, Any]] = []
        for a in accounts:
            row_dict: dict[str, Any] = {
                "platform_uid": a.platform_uid,
                "display_name": a.display_name,
                "primary_email": a.primary_email,
                "phone": a.phone,
                "birthday": a.birthday.isoformat() if a.birthday else "",
                "gender": a.gender.value if a.gender else "",
                "category": categories.get(a.category_id or "", ""),
                "tags": ", ".join(tags.get(tid, tid) for tid in a.tag_ids),
                "status": a.status.value,
                "device_name": a.assigned_device.external_id if a.assigned_device else "",
                "device_provider": a.assigned_device.provider if a.assigned_device else "",
                "preferred_app": a.preferred_app.value,
                "two_factor_enabled": "Yes" if a.two_factor_enabled else "No",
                "recovery_email": a.recovery_email or "",
                "country": a.country,
                "locale": a.locale,
                "timezone": a.timezone,
                "first_name": a.first_name,
                "last_name": a.last_name,
                "page_count": a.page_count,
                "group_count": a.group_count,
                "permission_state": a.permission_state.value,
                "security_state": a.security_state.value,
                "created_at": a.created_at.isoformat() if a.created_at else "",
                "last_login_at": a.last_login_at.isoformat() if a.last_login_at else "",
                "last_verified_at": a.last_verified_at.isoformat() if a.last_verified_at else "",
                "notes": a.notes,
            }
            # Strictly assert no secret keys in row
            secret_keys = contains_secret_fields(row_dict)
            if secret_keys:
                raise ValueError(f"Secret leakage prevention: forbidden fields {secret_keys}")
            filtered = {k: row_dict.get(k, "") for k in field_keys}
            records.append(filtered)

        if export_format == ExportFormat.CSV:
            return self._build_csv(records, field_keys)
        elif export_format == ExportFormat.XLSX:
            return self._build_xlsx(records, field_keys)
        elif export_format == ExportFormat.JSON:
            return self._build_json(records, field_keys)
        else:
            raise ValueError(f"Unsupported export format: {export_format}")

    def dry_run_import(
        self,
        raw_bytes: bytes,
        file_format: ExportFormat | None = None,
        filename: str | None = None,
    ) -> ImportDryRunResult:
        detected_format = file_format
        if detected_format is None and filename:
            lowered = filename.casefold()
            if lowered.endswith(".csv"):
                detected_format = ExportFormat.CSV
            elif lowered.endswith(".xlsx"):
                detected_format = ExportFormat.XLSX
            elif lowered.endswith(".json"):
                detected_format = ExportFormat.JSON

        if detected_format == ExportFormat.CSV:
            rows = self._parse_csv(raw_bytes)
        elif detected_format == ExportFormat.XLSX:
            rows = self._parse_xlsx(raw_bytes)
        elif detected_format == ExportFormat.JSON:
            rows = self._parse_json(raw_bytes)
        else:
            # Try auto-detect
            try:
                rows = self._parse_json(raw_bytes)
            except Exception:
                try:
                    rows = self._parse_xlsx(raw_bytes)
                except Exception:
                    rows = self._parse_csv(raw_bytes)

        existing_accounts = self._accounts.list_accounts()
        by_uid = {a.platform_uid.casefold(): a for a in existing_accounts if a.platform_uid}
        by_id = {a.id: a for a in existing_accounts}

        seen_uids_in_file: set[str] = set()
        evaluated_rows: list[ImportRowResult] = []
        valid_count = 0
        duplicate_count = 0
        error_count = 0

        for idx, row in enumerate(rows, start=1):
            errors: list[str] = []

            # 1. Check for secret fields
            found_secrets = contains_secret_fields(row)
            if found_secrets:
                secret_names = ", ".join(found_secrets)
                errors.append(f"Rejected: forbidden secret fields ({secret_names})")

            # 2. Extract key fields
            raw_uid = str(row.get("platform_uid") or row.get("uid") or "").strip()
            raw_name = str(row.get("display_name") or row.get("name") or "").strip()
            raw_email = str(row.get("primary_email") or row.get("email") or "").strip()

            if not raw_uid:
                errors.append("Missing required field: platform_uid / UID")
            if not raw_name:
                errors.append("Missing required field: display_name / Name")
            if not raw_email or "@" not in raw_email:
                errors.append("Missing or invalid primary email")

            # 3. Duplicate detection
            is_dup = False
            existing_account_id: str | None = None
            if raw_uid:
                uid_norm = raw_uid.casefold()
                if uid_norm in by_uid:
                    is_dup = True
                    existing_account_id = by_uid[uid_norm].id
                elif "id" in row and str(row["id"]) in by_id:
                    is_dup = True
                    existing_account_id = str(row["id"])
                elif uid_norm in seen_uids_in_file:
                    is_dup = True
                    errors.append(f"Duplicate UID '{raw_uid}' within the import file")
                seen_uids_in_file.add(uid_norm)

            # 4. Domain validation attempt
            if not errors:
                try:
                    onboarding_req = AccountOnboardingRequest(
                        source=OnboardingSource.AUTHORIZED_METADATA_IMPORT,
                        display_name=raw_name,
                        platform_uid=raw_uid,
                        primary_email=raw_email,
                        first_name=str(row.get("first_name", "")),
                        last_name=str(row.get("last_name", "")),
                        phone=str(row.get("phone", "")),
                        country=str(row.get("country", "")),
                        locale=str(row.get("locale", "")),
                        timezone=str(row.get("timezone", "UTC") or "UTC"),
                        status=AccountStatus(row["status"])
                        if row.get("status") in AccountStatus._value2member_map_
                        else AccountStatus.ACTIVE,
                        notes=str(row.get("notes", "")),
                    )
                    validate_onboarding_request(onboarding_req)
                except Exception as exc:
                    errors.append(str(exc))

            is_valid = len(errors) == 0
            if is_valid:
                valid_count += 1
            else:
                error_count += 1

            if is_dup:
                duplicate_count += 1

            evaluated_rows.append(
                ImportRowResult(
                    row_index=idx,
                    platform_uid=raw_uid,
                    display_name=raw_name,
                    is_valid=is_valid,
                    is_duplicate=is_dup,
                    existing_account_id=existing_account_id,
                    errors=tuple(errors),
                    normalized_data=row,
                )
            )

        return ImportDryRunResult(
            total_rows=len(rows),
            valid_count=valid_count,
            duplicate_count=duplicate_count,
            error_count=error_count,
            rows=tuple(evaluated_rows),
        )

    def execute_import(
        self,
        dry_run: ImportDryRunResult,
        conflict_strategy: ConflictStrategy = ConflictStrategy.SKIP,
    ) -> ImportExecutionResult:
        if conflict_strategy == ConflictStrategy.ERROR and dry_run.has_duplicates:
            msg = f"Import aborted: {dry_run.duplicate_count} duplicates detected"
            raise ValueError(msg)

        created_count = 0
        updated_count = 0
        skipped_count = 0
        errors: list[str] = []

        for row in dry_run.rows:
            if not row.is_valid:
                errors.append(f"Row {row.row_index} skipped due to errors: {', '.join(row.errors)}")
                continue

            data = row.normalized_data
            raw_uid = row.platform_uid
            raw_name = row.display_name
            raw_email = str(data.get("primary_email") or data.get("email") or "")

            if row.is_duplicate:
                if conflict_strategy == ConflictStrategy.SKIP:
                    skipped_count += 1
                    continue
                elif conflict_strategy == ConflictStrategy.OVERWRITE and row.existing_account_id:
                    existing = self._accounts.get_account(row.existing_account_id)
                    updated = replace(
                        existing,
                        display_name=raw_name or existing.display_name,
                        primary_email=raw_email or existing.primary_email,
                        phone=str(data.get("phone", existing.phone)),
                        first_name=str(data.get("first_name", existing.first_name)),
                        last_name=str(data.get("last_name", existing.last_name)),
                        country=str(data.get("country", existing.country)),
                        locale=str(data.get("locale", existing.locale)),
                        timezone=str(data.get("timezone", existing.timezone)),
                        notes=str(data.get("notes", existing.notes)),
                    )
                    self._accounts.save_account(updated)
                    updated_count += 1
                else:
                    skipped_count += 1
            else:
                account = self._accounts.create_account(
                    display_name=raw_name,
                    platform_uid=raw_uid,
                    primary_email=raw_email,
                )
                to_save = replace(
                    account,
                    phone=str(data.get("phone", "")),
                    first_name=str(data.get("first_name", "")),
                    last_name=str(data.get("last_name", "")),
                    country=str(data.get("country", "")),
                    locale=str(data.get("locale", "")),
                    timezone=str(data.get("timezone", "UTC") or "UTC"),
                    notes=str(data.get("notes", "")),
                    status=AccountStatus(data["status"])
                    if data.get("status") in AccountStatus._value2member_map_
                    else AccountStatus.ACTIVE,
                )
                self._accounts.save_account(to_save)
                created_count += 1

        return ImportExecutionResult(
            created_count=created_count,
            updated_count=updated_count,
            skipped_count=skipped_count,
            errors=tuple(errors),
        )

    def export_vault_archive(
        self,
        passphrase: str,
        account_ids: Sequence[str] | None = None,
    ) -> bytes:
        if not self._secrets:
            raise RuntimeError("Vault SecretService is not configured")
        if not passphrase or len(passphrase) < 8:
            raise ValueError("Passphrase must be at least 8 characters")

        all_accounts = self._accounts.list_accounts()
        if account_ids:
            target_ids = set(account_ids)
            accounts = [a for a in all_accounts if a.id in target_ids]
        else:
            accounts = list(all_accounts)

        payload_items = []
        if self._secret_repo_factory and self._unit_of_work:
            owner_ids = [a.id for a in accounts]
            with self._unit_of_work() as uow:
                repo = self._secret_repo_factory(uow)
                refs = repo.list_by_owner_ids(owner_ids)
            acct_map = {a.id: a for a in accounts}
            for ref in refs:
                account = acct_map.get(ref.owner_id)
                if not account:
                    continue
                val = self._secrets.reveal(ref)
                if val is not None:
                    payload_items.append(
                        {
                            "account_id": account.id,
                            "platform_uid": account.platform_uid,
                            "display_name": account.display_name,
                            "secret_type": ref.secret_type.value,
                            "value": val,
                        }
                    )

        container = {
            "version": 1,
            "archive_type": "sp_farms_vault_backup",
            "created_at": datetime.now(UTC).isoformat(),
            "count": len(payload_items),
            "items": payload_items,
        }
        raw_json = json.dumps(container)
        archive = encrypt_secret(raw_json, passphrase)
        return archive.to_json().encode("utf-8")

    def import_vault_archive(
        self,
        archive_bytes: bytes,
        passphrase: str,
    ) -> int:
        if not self._secrets:
            raise RuntimeError("Vault SecretService is not configured")
        archive = EncryptedSecretArchive.from_json(archive_bytes.decode("utf-8"))
        try:
            decrypted_json = decrypt_secret(archive, passphrase)
        except Exception as exc:
            raise ValueError(f"Invalid passphrase or corrupted vault archive: {exc}") from exc
        container = json.loads(decrypted_json)
        if container.get("archive_type") != "sp_farms_vault_backup":
            raise ValueError("Invalid vault backup archive type")

        items = container.get("items", [])
        existing_accounts = self._accounts.list_accounts()
        by_uid = {a.platform_uid: a for a in existing_accounts}
        by_id = {a.id: a for a in existing_accounts}

        restored_count = 0
        for item in items:
            account = by_id.get(item.get("account_id")) or by_uid.get(item.get("platform_uid"))
            if not account:
                continue

            sec_type_str = item.get("secret_type", "password")
            try:
                secret_type = SecretType(sec_type_str)
            except ValueError:
                secret_type = SecretType.PASSWORD
            secret_val = item.get("value")
            if secret_val:
                ref = self._secrets.create_reference(secret_type, account.id, secret_val)
                if self._secret_repo_factory and self._unit_of_work:
                    with self._unit_of_work() as uow:
                        repo = self._secret_repo_factory(uow)
                        repo.save(ref)
                        uow.commit()
                if secret_type in {SecretType.RECOVERY_SECRET} or "totp" in sec_type_str:
                    updated = replace(account, two_factor_enabled=True)
                    self._accounts.save_account(updated)
                restored_count += 1

        return restored_count

    # --- Low-level builders & parsers ---

    def _build_csv(self, records: Sequence[dict[str, Any]], field_keys: Sequence[str]) -> bytes:
        buf = io.StringIO()
        headers = [EXPORT_FIELD_LABELS.get(k, k) for k in field_keys]
        writer = csv.writer(buf, lineterminator="\r\n")
        writer.writerow(headers)
        for r in records:
            writer.writerow([r.get(k, "") for k in field_keys])
        # UTF-8 with BOM for Excel compatibility on Windows
        return b"\xef\xbb\xbf" + buf.getvalue().encode("utf-8")

    def _build_json(self, records: Sequence[dict[str, Any]], field_keys: Sequence[str]) -> bytes:
        payload = {
            "schema_version": "1.0",
            "exported_at": datetime.now(UTC).isoformat(),
            "count": len(records),
            "fields": list(field_keys),
            "accounts": list(records),
        }
        return json.dumps(payload, indent=2).encode("utf-8")

    def _build_xlsx(self, records: Sequence[dict[str, Any]], field_keys: Sequence[str]) -> bytes:
        buf = io.BytesIO()
        headers = [EXPORT_FIELD_LABELS.get(k, k) for k in field_keys]
        rows = [[str(r.get(k, "")) for k in field_keys] for r in records]

        content_types = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">\n'
            '  <Default Extension="rels" '
            'ContentType="application/vnd.openxmlformats-package.relationships+xml"/>\n'
            '  <Default Extension="xml" ContentType="application/xml"/>\n'
            '  <Override PartName="/xl/workbook.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>\n'
            '  <Override PartName="/xl/worksheets/sheet1.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>\n'
            "</Types>"
        )

        root_rels = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n'
            '  <Relationship Id="rId1" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/'
            'relationships/officeDocument" '
            'Target="xl/workbook.xml"/>\n'
            "</Relationships>"
        )

        wb_rels = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n'
            '  <Relationship Id="rId1" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
            'Target="worksheets/sheet1.xml"/>\n'
            "</Relationships>"
        )

        wb_xml = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">\n'
            "  <sheets>\n"
            '    <sheet name="Accounts" sheetId="1" r:id="rId1"/>\n'
            "  </sheets>\n"
            "</workbook>"
        )

        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("[Content_Types].xml", content_types)
            zf.writestr("_rels/.rels", root_rels)
            zf.writestr("xl/_rels/workbook.xml.rels", wb_rels)
            zf.writestr("xl/workbook.xml", wb_xml)

            sheet_lines = [
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
                '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">',
                "<sheetData>",
            ]
            all_rows = [headers] + rows
            for r_idx, row_vals in enumerate(all_rows, start=1):
                sheet_lines.append(f'<row r="{r_idx}">')
                for c_idx, val in enumerate(row_vals, start=1):
                    col_letter = chr(64 + c_idx) if c_idx <= 26 else f"A{chr(64 + c_idx - 26)}"
                    ref = f"{col_letter}{r_idx}"
                    escaped = (
                        val.replace("&", "&amp;")
                        .replace("<", "&lt;")
                        .replace(">", "&gt;")
                        .replace('"', "&quot;")
                    )
                    sheet_lines.append(f'<c r="{ref}" t="inlineStr"><is><t>{escaped}</t></is></c>')
                sheet_lines.append("</row>")
            sheet_lines.append("</sheetData></worksheet>")
            zf.writestr("xl/worksheets/sheet1.xml", "".join(sheet_lines))

        return buf.getvalue()

    def _parse_csv(self, raw_bytes: bytes) -> list[dict[str, Any]]:
        text = raw_bytes.decode("utf-8-sig", errors="replace")
        reader = csv.reader(io.StringIO(text))
        rows = list(reader)
        if not rows:
            return []
        raw_headers = rows[0]
        header_map = self._normalize_headers(raw_headers)
        result = []
        for row_vals in rows[1:]:
            if not any(v.strip() for v in row_vals):
                continue
            item = {}
            for col_idx, h in enumerate(header_map):
                if col_idx < len(row_vals):
                    item[h] = row_vals[col_idx].strip()
            result.append(item)
        return result

    def _parse_xlsx(self, raw_bytes: bytes) -> list[dict[str, Any]]:
        zf = zipfile.ZipFile(io.BytesIO(raw_bytes))
        shared_strings: list[str] = []
        if "xl/sharedStrings.xml" in zf.namelist():
            sst_tree = ET.fromstring(zf.read("xl/sharedStrings.xml"))
            for si in sst_tree.iter():
                if si.tag.endswith("si"):
                    text_parts = [t.text or "" for t in si.iter() if t.tag.endswith("t")]
                    shared_strings.append("".join(text_parts))

        sheet_name = "xl/worksheets/sheet1.xml"
        if sheet_name not in zf.namelist():
            sheets = [s for s in zf.namelist() if s.startswith("xl/worksheets/")]
            if not sheets:
                return []
            sheet_name = sheets[0]

        sheet_tree = ET.fromstring(zf.read(sheet_name))
        raw_rows: list[list[str]] = []
        for row_el in sheet_tree.iter():
            if row_el.tag.endswith("row"):
                row: list[str] = []
                for cell_el in row_el.iter():
                    if cell_el.tag.endswith("c"):
                        t = cell_el.attrib.get("t")
                        val = ""
                        if t == "inlineStr":
                            val = "".join(cell_el.itertext())
                        elif t == "s":
                            v_el = next((c for c in cell_el if c.tag.endswith("v")), None)
                            if v_el is not None and v_el.text:
                                idx = int(v_el.text)
                                val = shared_strings[idx] if idx < len(shared_strings) else ""
                        else:
                            v_el = next((c for c in cell_el if c.tag.endswith("v")), None)
                            if v_el is not None:
                                val = v_el.text or ""
                        row.append(val.strip())
                raw_rows.append(row)

        if not raw_rows:
            return []

        header_map = self._normalize_headers(raw_rows[0])
        result = []
        for row_vals in raw_rows[1:]:
            if not any(row_vals):
                continue
            item = {}
            for col_idx, h in enumerate(header_map):
                if col_idx < len(row_vals):
                    item[h] = row_vals[col_idx]
            result.append(item)
        return result

    def _parse_json(self, raw_bytes: bytes) -> list[dict[str, Any]]:
        loaded = json.loads(raw_bytes.decode("utf-8"))
        if isinstance(loaded, list):
            return loaded
        elif isinstance(loaded, dict):
            if "accounts" in loaded and isinstance(loaded["accounts"], list):
                return loaded["accounts"]
            elif "account" in loaded and isinstance(loaded["account"], dict):
                return [loaded["account"]]
            return [loaded]
        return []

    def _normalize_headers(self, headers: Sequence[str]) -> list[str]:
        label_to_key = {v.casefold(): k for k, v in EXPORT_FIELD_LABELS.items()}
        # Common aliases
        label_to_key["uid"] = "platform_uid"
        label_to_key["platform uid"] = "platform_uid"
        label_to_key["name"] = "display_name"
        label_to_key["display name"] = "display_name"
        label_to_key["email"] = "primary_email"
        label_to_key["primary email"] = "primary_email"
        label_to_key["phone"] = "phone"
        label_to_key["category"] = "category"
        label_to_key["status"] = "status"

        normalized: list[str] = []
        for h in headers:
            clean = h.strip()
            norm = clean.casefold()
            key = label_to_key.get(norm, clean.replace(" ", "_").casefold())
            normalized.append(key)
        return normalized
