from collections.abc import Callable, Sequence
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import uuid4

from sp_farms.application.accounts import AccountRepository
from sp_farms.application.device_pool import DevicePoolRepository
from sp_farms.application.device_profiles import DeviceProfileRepository
from sp_farms.application.device_service import DeviceService
from sp_farms.application.ports import Clock
from sp_farms.application.unit_of_work import UnitOfWork
from sp_farms.domain.device_pool import (
    AccountWorkspaceLock,
    DevicePoolPolicy,
    DevicePoolState,
    PoolDevice,
    QueuedRestoreItem,
    SchedulingPolicy,
)
from sp_farms.domain.device_restore import RestoreWorkspaceResult

if TYPE_CHECKING:
    from sp_farms.application.restore_workspace_service import RestoreWorkspaceService


class DevicePoolService:
    def __init__(
        self,
        unit_of_work_factory: Callable[[], UnitOfWork],
        pool_repo_factory: Callable[[UnitOfWork], DevicePoolRepository],
        account_repo_factory: Callable[[UnitOfWork], AccountRepository],
        device_profile_repo_factory: Callable[[UnitOfWork], DeviceProfileRepository],
        device_service: DeviceService,
        restore_service: "RestoreWorkspaceService",
        clock: Clock,
    ) -> None:
        self._unit_of_work = unit_of_work_factory
        self._pool_repo = pool_repo_factory
        self._account_repo = account_repo_factory
        self._profile_repo = device_profile_repo_factory
        self._devices = device_service
        self._restore_service = restore_service
        self._clock = clock

        self._queue: list[QueuedRestoreItem] = []
        self._device_last_used: dict[str, datetime] = {}
        self._round_robin_index: int = 0
        self._maintenance_devices: set[str] = set()

    # --- Policy Management ---

    def get_active_policy(self) -> DevicePoolPolicy:
        with self._unit_of_work() as uow:
            policy = self._pool_repo(uow).get_active_policy()
            if policy is None:
                policy = DevicePoolPolicy(
                    id="default",
                    name="Default Policy",
                    policy=SchedulingPolicy.BOUND_DEVICE_FIRST,
                    preferred_provider_order=("ldplayer", "mumu", "physical"),
                    allow_fallback=True,
                    max_concurrent_restores=2,
                    is_active=True,
                )
                self._pool_repo(uow).save_policy(policy)
                uow.commit()
            return policy

    def set_active_policy(self, policy: DevicePoolPolicy) -> None:
        with self._unit_of_work() as uow:
            self._pool_repo(uow).save_policy(policy)
            uow.commit()

    # --- Maintenance Mode ---

    def set_maintenance(self, device_key: str, maintenance: bool) -> None:
        if maintenance:
            self._maintenance_devices.add(device_key)
        else:
            self._maintenance_devices.discard(device_key)

    def is_in_maintenance(self, device_key: str) -> bool:
        return device_key in self._maintenance_devices

    # --- Device Discovery and Pool States ---

    def list_pool_devices(self) -> Sequence[PoolDevice]:
        now = self._clock.now()
        discovered = self._devices.discover()
        with self._unit_of_work() as uow:
            active_locks = {
                lock.device_key: lock for lock in self._pool_repo(uow).list_active_locks(now)
            }

        pool_devices: list[PoolDevice] = []
        for dev in discovered:
            key = f"{dev.provider.value}:{dev.external_id}"
            in_maint = key in self._maintenance_devices
            lock = active_locks.get(key)
            adb_ready = bool(dev.is_online and dev.adb_serial)

            if in_maint:
                state = DevicePoolState.MAINTENANCE
            elif not dev.is_online:
                state = DevicePoolState.OFFLINE
            elif lock is not None:
                state = DevicePoolState.IN_USE
            elif adb_ready:
                state = DevicePoolState.AVAILABLE
            else:
                state = DevicePoolState.STARTING

            pdev = PoolDevice(
                device_key=key,
                provider=dev.provider.value,
                external_id=dev.external_id,
                display_name=dev.display_name,
                state=state,
                is_online=dev.is_online,
                adb_ready=adb_ready,
                in_maintenance=in_maint,
                last_available_at=self._device_last_used.get(key),
                current_account_id=lock.account_id if lock else None,
                reservation_job_id=lock.job_id if lock else None,
                reservation_expires_at=lock.expires_at if lock else None,
            )
            pool_devices.append(pdev)
        return pool_devices

    def get_available_devices(
        self,
        provider_filter: Sequence[str] | None = None,
    ) -> Sequence[PoolDevice]:
        all_devs = self.list_pool_devices()
        available = [d for d in all_devs if d.state == DevicePoolState.AVAILABLE]
        if provider_filter:
            available = [d for d in available if d.provider in provider_filter]
        return available

    # --- Queue & Scheduling ---

    def enqueue_restore(
        self,
        account_ids: Sequence[str],
        requested_device_id: str | None = None,
        scheduling_policy: SchedulingPolicy | None = None,
        preferred_app: str = "browser",
        priority: int = 0,
    ) -> Sequence[QueuedRestoreItem]:
        now = self._clock.now()
        policy = scheduling_policy or self.get_active_policy().policy
        items: list[QueuedRestoreItem] = []
        for acct_id in account_ids:
            # Check if already queued
            if any(q.account_id == acct_id and q.status == "queued" for q in self._queue):
                continue
            item = QueuedRestoreItem(
                account_id=acct_id,
                requested_device_id=requested_device_id,
                scheduling_policy=policy,
                preferred_app=preferred_app,
                priority=priority,
                enqueued_at=now,
                status="queued",
            )
            self._queue.append(item)
            items.append(item)
        # Sort queue by priority desc, enqueued_at asc
        self._queue.sort(key=lambda x: (-x.priority, x.enqueued_at))
        return items

    def list_queue(self) -> Sequence[QueuedRestoreItem]:
        return tuple(self._queue)

    def cancel_queue_item(self, account_id: str) -> bool:
        for item in self._queue:
            if item.account_id == account_id and item.status == "queued":
                item.status = "cancelled"
                return True
        return False

    def select_device_for_account(
        self,
        account_id: str,
        policy: SchedulingPolicy,
        available_devices: Sequence[PoolDevice],
        preferred_provider_order: Sequence[str] = ("ldplayer", "mumu", "physical"),
        allow_fallback: bool = True,
    ) -> PoolDevice | None:
        if not available_devices:
            return None

        # 1. BOUND_DEVICE_FIRST
        if policy == SchedulingPolicy.BOUND_DEVICE_FIRST:
            with self._unit_of_work() as uow:
                binding = self._profile_repo(uow).get_binding(account_id)
            if binding and binding.device_profile_id:
                with self._unit_of_work() as uow:
                    prof = self._profile_repo(uow).get_by_id(binding.device_profile_id)
                if prof:
                    target_key = f"{prof.provider.value}:{prof.external_id}"
                    for d in available_devices:
                        if d.device_key == target_key:
                            return d
            if not allow_fallback:
                return None
            # fallback to ANY_AVAILABLE
            return available_devices[0]

        # 2. LEAST_RECENTLY_USED
        elif policy == SchedulingPolicy.LEAST_RECENTLY_USED:
            # Device with oldest last_available_at (None means never used, prioritize it)
            def lru_key(d: PoolDevice) -> float:
                last = self._device_last_used.get(d.device_key)
                return last.timestamp() if last else 0.0

            return min(available_devices, key=lru_key)

        # 3. ROUND_ROBIN
        elif policy == SchedulingPolicy.ROUND_ROBIN:
            idx = self._round_robin_index % len(available_devices)
            self._round_robin_index += 1
            return available_devices[idx]

        # 4. PREFERRED_PROVIDER
        elif policy == SchedulingPolicy.PREFERRED_PROVIDER:
            for prov in preferred_provider_order:
                for d in available_devices:
                    if d.provider == prov:
                        return d
            if allow_fallback:
                return available_devices[0]
            return None

        # 5. ANY_AVAILABLE (default)
        else:
            return available_devices[0]

    # --- Lock / Lease Management ---

    def acquire_device_lock(
        self,
        account_id: str,
        device_key: str,
        job_id: str | None = None,
        ttl_seconds: int = 300,
    ) -> AccountWorkspaceLock | None:
        now = self._clock.now()
        with self._unit_of_work() as uow:
            lock = self._pool_repo(uow).acquire_lock(
                account_id=account_id,
                device_key=device_key,
                job_id=job_id,
                now=now,
                ttl_seconds=ttl_seconds,
            )
            if lock:
                uow.commit()
            return lock

    def release_device_lock(
        self,
        account_id: str,
    ) -> bool:
        now = self._clock.now()
        with self._unit_of_work() as uow:
            lock = self._pool_repo(uow).get_lock_by_account(account_id)
            if lock:
                self._device_last_used[lock.device_key] = now
            success = self._pool_repo(uow).release_lock(account_id)
            if success:
                uow.commit()
            return success

    def release_device_and_restore_next(
        self,
        account_id: str,
    ) -> tuple[bool, RestoreWorkspaceResult | None]:
        released = self.release_device_lock(account_id)
        next_result: RestoreWorkspaceResult | None = None
        if released:
            next_result = self.dispatch_next()
        return released, next_result

    def release_device_by_key(
        self,
        device_key: str,
    ) -> bool:
        now = self._clock.now()
        with self._unit_of_work() as uow:
            lock = self._pool_repo(uow).get_lock_by_device(device_key)
            if lock:
                self._device_last_used[device_key] = now
                success = self._pool_repo(uow).release_lock(lock.account_id)
                if success:
                    uow.commit()
                return success
        return False

    def recover_stale_locks(self) -> int:
        now = self._clock.now()
        with self._unit_of_work() as uow:
            count = self._pool_repo(uow).release_stale_locks(now)
            if count > 0:
                uow.commit()
            return count

    # --- Step / Worker Dispatch ---

    def dispatch_next(self) -> RestoreWorkspaceResult | None:
        """Finds next eligible queued account and available device, acquires lock, and restores."""
        # Purge stale locks first
        self.recover_stale_locks()

        active_policy = self.get_active_policy()
        available_devices = self.get_available_devices()
        if not available_devices:
            return None

        queued_items = [q for q in self._queue if q.status == "queued"]
        if not queued_items:
            return None

        for item in queued_items:
            selected_device: PoolDevice | None = None
            if item.requested_device_id:
                for device in available_devices:
                    if item.requested_device_id in (device.device_key, device.external_id):
                        selected_device = device
                        break
            else:
                selected_device = self.select_device_for_account(
                    account_id=item.account_id,
                    policy=item.scheduling_policy,
                    available_devices=available_devices,
                    preferred_provider_order=active_policy.preferred_provider_order,
                    allow_fallback=active_policy.allow_fallback,
                )

            if selected_device is None:
                continue

            # Attempt to acquire lock atomically
            lock = self.acquire_device_lock(
                account_id=item.account_id,
                device_key=selected_device.device_key,
                job_id=str(uuid4()),
                ttl_seconds=300,
            )
            if lock is None:
                # Lock could not be acquired (conflict)
                continue

            # Update item status
            item.status = "restoring"
            item.assigned_device_key = selected_device.device_key

            # Perform restore
            try:
                result = self._restore_service.restore_workspace(
                    item.account_id, selected_device.device_key
                )
                if result.success:
                    item.status = "completed"
                else:
                    item.status = "failed"
                    item.error_message = result.message
                return result
            except Exception as e:
                item.status = "failed"
                item.error_message = str(e)
                self.release_device_lock(item.account_id)
                raise

        return None
