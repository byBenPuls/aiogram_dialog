from copy import copy
from typing import Dict, Optional, Type

from aiogram import Bot
from aiogram.enums import ChatMemberStatus
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.base import BaseStorage, StorageKey

from aiogram_dialog.api.entities import (
    AccessSettings, Context, DEFAULT_STACK_ID, Stack,
)
from aiogram_dialog.api.exceptions import UnknownIntent, UnknownState


class StorageProxy:
    def __init__(
            self,
            storage: BaseStorage,
            user_id: int,
            chat_id: int,
            chat_type: str,
            thread_id: Optional[int],
            bot: Bot,
            state_groups: Dict[str, Type[StatesGroup]],
    ):
        self.storage = storage
        self.state_groups = state_groups
        self.user_id = user_id
        self.chat_id = chat_id
        self.thread_id = thread_id
        self.chat_type = chat_type
        self.bot = bot

    async def load_context(self, intent_id: str) -> Context:
        data = await self.storage.get_data(
            key=self._context_key(intent_id),
        )
        if not data:
            raise UnknownIntent(
                f"Context not found for intent id: {intent_id}",
            )
        data["state"] = self._state(data["state"])
        return Context(**data)

    async def load_stack(self, stack_id: str = DEFAULT_STACK_ID) -> Stack:
        data = await self.storage.get_data(
            key=self._stack_key(stack_id),
        )
        if not data:
            return Stack(_id=stack_id)

        access_settings = self._parse_access_settings(
            data.pop("access_settings"),
        )
        return Stack(access_settings=access_settings, **data)

    async def save_context(self, context: Optional[Context]) -> None:
        if not context:
            return
        data = copy(vars(context))
        data["state"] = data["state"].state
        await self.storage.set_data(
            key=self._context_key(context.id),
            data=data,
        )

    async def remove_context(self, intent_id: str):
        await self.storage.set_data(
            key=self._context_key(intent_id),
            data={},
        )

    async def remove_stack(self, stack_id: str):
        await self.storage.set_data(
            key=self._stack_key(stack_id),
            data={},
        )

    async def save_stack(self, stack: Optional[Stack]) -> None:
        if not stack:
            return
        if stack.empty() and not stack.last_message_id:
            await self.storage.set_data(
                key=self._stack_key(stack.id),
                data={},
            )
        else:
            data = copy(vars(stack))
            data["access_settings"] = self._dump_access_settings(stack.access_settings)
            await self.storage.set_data(
                key=self._stack_key(stack.id),
                data=data,
            )

    def _context_key(self, intent_id: str) -> StorageKey:
        return StorageKey(
            bot_id=self.bot.id,
            chat_id=self.chat_id,
            user_id=self.user_id,
            thread_id=self.thread_id,
            destiny=f"aiogd:context:{intent_id}",
        )

    def _stack_key(self, stack_id: str) -> StorageKey:
        return StorageKey(
            bot_id=self.bot.id,
            chat_id=self.chat_id,
            user_id=self.user_id,
            thread_id=self.thread_id,
            destiny=f"aiogd:stack:{stack_id}",
        )

    def _state(self, state: str) -> State:
        group, *_ = state.partition(":")
        try:
            for real_state in self.state_groups[group].__all_states__:
                if real_state.state == state:
                    return real_state
        except KeyError:
            raise UnknownState(f"Unknown state group {group}")
        raise UnknownState(f"Unknown state {state}")

    def _parse_access_settings(
            self, raw: Optional[Dict],
    ) -> Optional[AccessSettings]:
        if not raw:
            return None
        if raw_member_status := raw.get("member_status"):
            member_status = ChatMemberStatus(raw_member_status)
        else:
            member_status = None
        return AccessSettings(
            user_ids=raw.get("user_ids") or [],
            member_status=member_status,
            custom=raw.get("custom")
        )

    def _dump_access_settings(
            self, access_settings: Optional[AccessSettings],
    ) -> Optional[Dict]:
        if not access_settings:
            return None
        return {
            "user_ids": access_settings.user_ids,
            "member_status": access_settings.member_status,
            "custom": access_settings.custom,
        }
