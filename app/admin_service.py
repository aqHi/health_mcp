"""Services for managing administrative users and dashboard data."""

from __future__ import annotations

import logging
import secrets
from typing import Optional, Tuple

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .config import get_settings
from .models import AdminUser, HealthMetric
from .security import hash_password, verify_password


class AdminUserService:
    """Encapsulate admin user lookups and credential management."""

    def __init__(self, session: Session):
        self.session = session

    def get_by_id(self, user_id: str) -> Optional[AdminUser]:
        return self.session.get(AdminUser, user_id)

    def get_by_username(self, username: str) -> Optional[AdminUser]:
        stmt = select(AdminUser).where(AdminUser.username == username)
        return self.session.execute(stmt).scalar_one_or_none()

    def authenticate(self, username: str, password: str) -> Optional[AdminUser]:
        user = self.get_by_username(username)
        if not user or not user.is_active:
            return None
        if not verify_password(password, user.password_hash):
            return None
        return user

    def create_user(self, username: str, password: str) -> AdminUser:
        user = AdminUser(username=username, password_hash=hash_password(password))
        self.session.add(user)
        self.session.flush()
        return user

    def set_password(self, user: AdminUser, password: str) -> AdminUser:
        user.password_hash = hash_password(password)
        self.session.add(user)
        self.session.flush()
        return user

    def upsert_credentials(self, username: str, password: str) -> Tuple[AdminUser, bool]:
        user = self.get_by_username(username)
        if user:
            self.set_password(user, password)
            return user, False
        created = self.create_user(username, password)
        return created, True

    def first_admin(self) -> Optional[AdminUser]:
        stmt = select(AdminUser).order_by(AdminUser.created_at.asc())
        return self.session.execute(stmt).scalars().first()

    def dashboard_stats(self) -> dict:
        total_metrics = self.session.execute(
            select(func.count()).select_from(HealthMetric).where(HealthMetric.deleted.is_(False))
        ).scalar_one()
        total_users = self.session.execute(
            select(func.count(func.distinct(HealthMetric.user_id))).where(HealthMetric.deleted.is_(False))
        ).scalar_one()
        type_counts = self.session.execute(
            select(HealthMetric.type_code, func.count())
            .where(HealthMetric.deleted.is_(False))
            .group_by(HealthMetric.type_code)
            .order_by(func.count().desc())
        ).all()
        return {
            "total_metrics": total_metrics or 0,
            "total_users": total_users or 0,
            "type_counts": type_counts,
        }


def ensure_default_admin(session: Session, logger: Optional[logging.Logger] = None) -> None:
    """Ensure at least one admin user exists, creating from env defaults."""

    settings = get_settings()
    service = AdminUserService(session)
    logger = logger or logging.getLogger(__name__)

    env_username = settings.admin_username
    env_password = settings.admin_password

    if env_username and env_password:
        service.upsert_credentials(env_username, env_password)
        logger.info("Admin 用户 %s 已根据环境变量完成配置", env_username)
        return

    existing = service.first_admin()
    if existing:
        logger.info("已检测到管理员账号 %s，跳过默认创建", existing.username)
        return

    username = settings.default_admin_username or "admin"
    if service.get_by_username(username):
        username = f"{username}-{secrets.randbelow(10_000):04d}"
    password = secrets.token_urlsafe(12)
    service.create_user(username, password)
    logger.warning(
        "未提供管理员环境变量，已生成默认账号 username='%s' password='%s'",
        username,
        password,
    )
