import hashlib
from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

from sp_farms.domain.accounts import (
    Account,
    AccountGender,
    AccountStatus,
    PermissionState,
    PreferredApp,
    SecurityState,
)
from sp_farms.domain.content import MediaAsset, MediaMetadata, MediaType
from sp_farms.domain.device_management import DeviceProfile
from sp_farms.domain.jobs import Job, JobState
from sp_farms.domain.providers import DeviceProviderType
from sp_farms.infrastructure.database import (
    AccountModel,
    Database,
    DeviceProfileModel,
    JobModel,
    MediaAssetModel,
)


def generate_synthetic_accounts(count: int, start_idx: int = 1) -> list[Account]:
    """Generate realistic synthetic operator accounts for scale and benchmark testing."""
    accounts: list[Account] = []
    now = datetime.now(UTC)

    first_names = [
        "Alex",
        "Jordan",
        "Taylor",
        "Morgan",
        "Sam",
        "Chris",
        "Casey",
        "Pat",
        "Riley",
        "Jesse",
    ]
    last_names = [
        "Smith",
        "Johnson",
        "Williams",
        "Brown",
        "Jones",
        "Garcia",
        "Miller",
        "Davis",
        "Rodriguez",
        "Martinez",
    ]
    statuses = [
        AccountStatus.ACTIVE,
        AccountStatus.ACTIVE,
        AccountStatus.ACTIVE,
        AccountStatus.ATTENTION,
        AccountStatus.DISABLED,
    ]
    locales = ["en_US", "km_KH", "th_TH", "vi_VN"]

    for i in range(start_idx, start_idx + count):
        first = first_names[i % len(first_names)]
        last = last_names[(i // len(first_names)) % len(last_names)]
        display_name = f"{first} {last} {i}"
        uid = f"1000{i:08d}"
        email = f"operator.acc{i}@spfarms.test"
        status = statuses[i % len(statuses)]
        locale = locales[i % len(locales)]

        accounts.append(
            Account(
                id=str(uuid4()),
                display_name=display_name,
                first_name=first,
                last_name=last,
                platform_uid=uid,
                primary_email=email,
                phone=f"+1555{i % 10000000:07d}",
                country="US" if locale == "en_US" else "KH",
                locale=locale,
                timezone="America/New_York" if locale == "en_US" else "Asia/Phnom_Penh",
                status=status,
                two_factor_enabled=(i % 2 == 0),
                preferred_app=PreferredApp.BROWSER if i % 2 == 0 else PreferredApp.FACEBOOK,
                permission_state=PermissionState.COMPLETE
                if i % 3 != 0
                else PermissionState.UNKNOWN,
                security_state=SecurityState.SECURE
                if status == AccountStatus.ACTIVE
                else SecurityState.UNKNOWN,
                birthday=date(1990 + (i % 20), 1 + (i % 12), 1 + (i % 28)),
                gender=AccountGender.MALE if i % 2 == 0 else AccountGender.FEMALE,
                notes=f"Synthetic test account #{i}",
                page_count=i % 10,
                group_count=i % 25,
                created_at=now - timedelta(days=i % 365),
                updated_at=now,
            )
        )
    return accounts


def generate_synthetic_jobs(count: int, start_idx: int = 1) -> list[Job]:
    """Generate synthetic jobs across various states and job types."""
    jobs: list[Job] = []
    now = datetime.now(UTC)

    job_types = [
        "mobile_publishing",
        "profile_sync",
        "media_prep",
        "workspace_backup",
        "health_audit",
    ]
    states = [
        JobState.QUEUED,
        JobState.RUNNING,
        JobState.SUCCEEDED,
        JobState.FAILED,
        JobState.CANCELLED,
    ]

    for i in range(start_idx, start_idx + count):
        j_type = job_types[i % len(job_types)]
        state = states[i % len(states)]
        progress = (
            100
            if state == JobState.SUCCEEDED
            else (0 if state == JobState.QUEUED else (i % 99 + 1))
        )

        jobs.append(
            Job(
                id=str(uuid4()),
                job_type=j_type,
                target_type="account" if i % 2 == 0 else "device",
                target_id=f"target_{i % 500}",
                state=state,
                progress=progress,
                attempt_count=1 if state != JobState.QUEUED else 0,
                max_attempts=3,
                idempotency_key=f"idem_{i}_{uuid4().hex[:8]}",
                error_code=None if state != JobState.FAILED else "DEVICE_TIMEOUT",
                error_message=None if state != JobState.FAILED else "Execution timed out",
                next_retry_at=None,
                created_at=now - timedelta(hours=i % 720),
                updated_at=now,
            )
        )
    return jobs


def generate_synthetic_assets(count: int, start_idx: int = 1) -> list[MediaAsset]:
    """Generate synthetic media asset records."""
    assets: list[MediaAsset] = []
    now = datetime.now(UTC)
    folders = ["campaigns", "products", "lifestyle", "announcements", "general"]

    for i in range(start_idx, start_idx + count):
        is_video = i % 5 == 0
        m_type = MediaType.VIDEO if is_video else MediaType.IMAGE
        ext = "mp4" if is_video else "png"
        folder = folders[i % len(folders)]
        file_name = f"asset_{i:06d}.{ext}"
        fake_content = f"content_seed_{i}_{folder}".encode()
        sha256 = hashlib.sha256(fake_content).hexdigest()

        meta = MediaMetadata(
            mime_type="video/mp4" if is_video else "image/png",
            file_size_bytes=1024 * (50 + (i % 1000)),
            sha256_hash=sha256,
            width=1920 if is_video else 1080,
            height=1080,
            duration_seconds=30.0 if is_video else None,
            aspect_ratio="16:9",
        )

        assets.append(
            MediaAsset(
                id=str(uuid4()),
                file_path=f"C:/assets/{folder}/{file_name}",
                file_name=file_name,
                media_type=m_type,
                metadata=meta,
                thumbnail_path=f"C:/cache/thumbnails/{sha256}.jpg",
                folder=folder,
                tags=(folder, "synthetic", "batch"),
                is_favorite=(i % 7 == 0),
                is_archived=False,
                created_at=now - timedelta(days=i % 180),
                updated_at=now,
            )
        )
    return assets


def generate_synthetic_devices(count: int, start_idx: int = 1) -> list[DeviceProfile]:
    """Generate synthetic device profiles."""
    devices: list[DeviceProfile] = []
    now = datetime.now(UTC)
    providers = [DeviceProviderType.PHYSICAL, DeviceProviderType.LDPLAYER, DeviceProviderType.MUMU]

    for i in range(start_idx, start_idx + count):
        prov = providers[i % len(providers)]
        ext_id = f"dev_serial_{prov.value}_{i:04d}"

        devices.append(
            DeviceProfile(
                provider=prov,
                external_id=ext_id,
                friendly_name=f"Farm Device #{i} ({prov.value})",
                emulator_instance=f"instance_{i}" if prov != DeviceProviderType.PHYSICAL else "",
                adb_serial=f"127.0.0.1:{5555 + i}",
                android_version="12.0",
                model="Pixel 6" if i % 2 == 0 else "Galaxy S22",
                resolution="1080x2400",
                dpi=420,
                language="en",
                locale="en_US",
                timezone="UTC",
                created_at=now,
                updated_at=now,
            )
        )
    return devices


def populate_synthetic_database(
    database: Database,
    account_count: int = 1000,
    job_count: int = 1000,
    asset_count: int = 500,
    device_count: int = 100,
) -> dict[str, int]:
    """High-speed bulk populator that inserts synthetic records using chunked transactions."""
    accounts = generate_synthetic_accounts(account_count)
    jobs = generate_synthetic_jobs(job_count)
    assets = generate_synthetic_assets(asset_count)
    devices = generate_synthetic_devices(device_count)

    with database.unit_of_work() as unit:
        session = unit._active_session()

        # Bulk save accounts
        for acc in accounts:
            session.add(
                AccountModel(
                    id=acc.id,
                    display_name=acc.display_name,
                    first_name=acc.first_name,
                    last_name=acc.last_name,
                    platform_uid=acc.platform_uid,
                    birthday=acc.birthday,
                    gender=acc.gender.value if acc.gender else None,
                    primary_email=acc.primary_email,
                    recovery_email=acc.recovery_email,
                    phone=acc.phone,
                    country=acc.country,
                    locale=acc.locale,
                    timezone=acc.timezone,
                    account_created_at=acc.account_created_at,
                    status=acc.status.value,
                    two_factor_enabled=acc.two_factor_enabled,
                    category_id=acc.category_id,
                    notes=acc.notes,
                    preferred_app=acc.preferred_app.value,
                    last_login_at=acc.last_login_at,
                    last_verified_at=acc.last_verified_at,
                    page_count=acc.page_count,
                    group_count=acc.group_count,
                    permission_state=acc.permission_state.value,
                    security_state=acc.security_state.value,
                    created_at=acc.created_at,
                    updated_at=acc.updated_at,
                )
            )

        # Bulk save jobs
        for job in jobs:
            session.add(JobModel.from_job(job))

        # Bulk save assets
        for asset in assets:
            session.add(MediaAssetModel.from_asset(asset))

        # Bulk save devices
        for dev in devices:
            session.add(
                DeviceProfileModel(
                    id=dev.id,
                    provider=dev.provider.value,
                    external_id=dev.external_id,
                    friendly_name=dev.friendly_name,
                    emulator_instance=dev.emulator_instance,
                    adb_serial=dev.adb_serial,
                    android_version=dev.android_version,
                    model=dev.model,
                    resolution=dev.resolution,
                    dpi=dev.dpi,
                    language=dev.language,
                    locale=dev.locale,
                    timezone=dev.timezone,
                    preferred_app=dev.preferred_app.value,
                    created_at=dev.created_at,
                    updated_at=dev.updated_at,
                )
            )

        unit.commit()

    return {
        "accounts": len(accounts),
        "jobs": len(jobs),
        "assets": len(assets),
        "devices": len(devices),
    }
