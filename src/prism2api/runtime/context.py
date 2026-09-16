"""Context Manager and Resource Lease for M04 Context Isolation."""

from enum import Enum
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field

from prism2api.storage.db import get_db_connection
from prism2api.storage.journal import get_iso_now


class ContextPolicy(str, Enum):
    ISOLATED = "isolated"
    EXPLICIT = "explicit"


class ContextBinding(BaseModel):
    context_id: str
    principal_id: str
    auth_profile_id: str
    context_policy: ContextPolicy
    workspace_ref: Optional[str] = None
    conversation_ref: Optional[str] = None
    context_revision: int = 1
    busy_run_id: Optional[str] = None
    lease_epoch: int = 0
    created_at: str = Field(default_factory=get_iso_now)


class ResourceLease(BaseModel):
    lease_id: str
    context_id: str
    run_id: str
    owner_epoch: int
    is_active: bool = True


class ContextBusyError(Exception):
    """Raised when context is already busy with another active run."""
    pass


class ContextManager:
    """Manages context bindings, leases, and isolation boundaries."""

    def __init__(self, db_conn):
        self.conn = db_conn

    def create_context(
        self,
        context_id: str,
        principal_id: str,
        auth_profile_id: str,
        policy: ContextPolicy,
        workspace_ref: Optional[str] = None,
        conversation_ref: Optional[str] = None,
    ) -> ContextBinding:
        """Create and store a new context binding."""
        now = get_iso_now()
        binding = ContextBinding(
            context_id=context_id,
            principal_id=principal_id,
            auth_profile_id=auth_profile_id,
            context_policy=policy,
            workspace_ref=workspace_ref,
            conversation_ref=conversation_ref,
            created_at=now,
        )
        with self.conn:
            self.conn.execute(
                """
                INSERT INTO contexts
                (context_id, principal_id, auth_profile_id, context_policy, workspace_ref, conversation_ref, context_revision, busy_run_id, lease_epoch, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    binding.context_id,
                    binding.principal_id,
                    binding.auth_profile_id,
                    binding.context_policy.value,
                    binding.workspace_ref,
                    binding.conversation_ref,
                    binding.context_revision,
                    binding.busy_run_id,
                    binding.lease_epoch,
                    binding.created_at,
                ),
            )
        return binding

    def get_context(self, context_id, principal_id=None, auth_profile_id=None):
        with self.conn:
            row = self.conn.execute("SELECT * FROM contexts WHERE context_id=?", (context_id,)).fetchone()
        if row is None or (principal_id is not None and row["principal_id"] != principal_id) or (
            auth_profile_id is not None and row["auth_profile_id"] != auth_profile_id
        ):
            raise KeyError("Context not found")
        data = dict(row)
        data["policy"] = data.pop("context_policy")
        return ContextBinding(context_policy=data.pop("policy"), **data)

    def assert_lease(self, lease):
        binding = self.get_context(lease.context_id)
        if not lease.is_active or binding.busy_run_id != lease.run_id or binding.lease_epoch != lease.owner_epoch:
            raise ContextBusyError("Stale context lease")
        return binding

    def bind_remote(self, lease, handle):
        with self.conn:
            current = self.assert_lease(lease)
            for key in ("workspace_ref", "conversation_ref"):
                old, new = getattr(current, key), getattr(handle, key)
                if old is not None and old != new:
                    raise ContextBusyError("Remote context identity changed")
            self.conn.execute("UPDATE contexts SET workspace_ref=?, conversation_ref=? WHERE context_id=?",
                              (handle.workspace_ref, handle.conversation_ref, lease.context_id))
        return self.get_context(lease.context_id)

    def acquire_lease(self, context_id: str, run_id: str) -> ResourceLease:
        """Acquire single-owner resource lease using compare-and-swap."""
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT busy_run_id, lease_epoch FROM contexts WHERE context_id = ?",
            (context_id,),
        )
        row = cursor.fetchone()
        if not row:
            raise ValueError(f"Context {context_id} not found.")

        busy_run_id, current_epoch = row["busy_run_id"], row["lease_epoch"]
        if busy_run_id is not None and busy_run_id != run_id:
            raise ContextBusyError(
                f"Context {context_id} is busy with run_id {busy_run_id}."
            )

        new_epoch = current_epoch + 1
        with self.conn:
            cursor.execute(
                """
                UPDATE contexts
                SET busy_run_id = ?, lease_epoch = ?
                WHERE context_id = ? AND lease_epoch = ?
                """,
                (run_id, new_epoch, context_id, current_epoch),
            )
            if cursor.rowcount == 0:
                raise ContextBusyError(f"Lease collision on context {context_id}.")

        lease_id = f"lease_{context_id}_{new_epoch}"
        return ResourceLease(
            lease_id=lease_id,
            context_id=context_id,
            run_id=run_id,
            owner_epoch=new_epoch,
            is_active=True,
        )

    def release_lease(self, lease: ResourceLease) -> bool:
        """Compare-and-release lease. Does not throw if already released."""
        cursor = self.conn.cursor()
        with self.conn:
            cursor.execute(
                """
                UPDATE contexts
                SET busy_run_id = NULL
                WHERE context_id = ? AND busy_run_id = ? AND lease_epoch = ?
                """,
                (lease.context_id, lease.run_id, lease.owner_epoch),
            )
            released = cursor.rowcount > 0
        lease.is_active = False
        return released

    @staticmethod
    def verify_isolation(context_a_text: str, context_b_text: str, nonce_a: str, nonce_b: str) -> bool:
        """Verify that context B does not contain nonce A and vice versa."""
        return (nonce_a not in context_b_text) and (nonce_b not in context_a_text)
