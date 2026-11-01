# -*- coding: utf-8 -*-
"""
حزمة معالجات رسائل بروتوكول ComposeBridge WebSocket.
Package containing modular WebSocket message handlers.
"""

from .apk_delivery_handler import HANDLERS as APK_HANDLERS
from .element_analysis_handler import HANDLERS as ELEMENT_HANDLERS
from .batch_edits_handler import HANDLERS as BATCH_HANDLERS
from .files_review_handler import HANDLERS as FILES_HANDLERS
from .state_sync_handler import HANDLERS as STATE_HANDLERS

ALL_HANDLERS = {}
ALL_HANDLERS.update(STATE_HANDLERS)
ALL_HANDLERS.update(ELEMENT_HANDLERS)
ALL_HANDLERS.update(BATCH_HANDLERS)
ALL_HANDLERS.update(FILES_HANDLERS)
ALL_HANDLERS.update(APK_HANDLERS)
