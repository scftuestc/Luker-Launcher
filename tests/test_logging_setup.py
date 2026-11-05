import logging
import sys
import tempfile
import threading
import unittest
from logging.handlers import RotatingFileHandler
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from luker_launcher.infrastructure import logging_setup


class LoggingSetupTests(unittest.TestCase):
    def setUp(self):
        self.root = logging.getLogger()
        self.original_handlers = self.root.handlers[:]
        self.original_level = self.root.level
        self.original_excepthook = sys.excepthook
        self.original_thread_excepthook = threading.excepthook
        self.addCleanup(self._restore_logging)

        configured = patch.object(logging_setup, '_configured', False)
        configured.start()
        self.addCleanup(configured.stop)
        ui_handler = patch.object(logging_setup, '_ui_handler', None)
        ui_handler.start()
        self.addCleanup(ui_handler.stop)

    def _restore_logging(self):
        for handler in self.root.handlers:
            if handler not in self.original_handlers:
                self.root.removeHandler(handler)
                handler.close()
        self.root.handlers = self.original_handlers
        self.root.setLevel(self.original_level)
        sys.excepthook = self.original_excepthook
        threading.excepthook = self.original_thread_excepthook

    def _added_handlers(self) -> list[logging.Handler]:
        return [h for h in self.root.handlers if h not in self.original_handlers]

    def _close_added_handlers(self) -> list[logging.Handler]:
        """先摘除并关闭文件 handler，Windows 才允许删除临时目录。"""
        handlers = self._added_handlers()
        for handler in handlers:
            self.root.removeHandler(handler)
            handler.close()
        return handlers

    def test_creates_log_file_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as app_dir:
            with (
                patch.object(logging_setup, 'get_app_dir', return_value=Path(app_dir)),
                patch.object(
                    logging_setup.tempfile,
                    'gettempdir',
                    return_value=str(Path(app_dir) / 'unused'),
                ),
            ):
                logging_setup.setup_logging()
                logging_setup.setup_logging()

            log_path = Path(app_dir) / logging_setup.LOG_FILE_NAME
            handlers = self._close_added_handlers()

            self.assertTrue(log_path.exists())
            self.assertEqual(len(handlers), 1)
            self.assertIsInstance(handlers[0], RotatingFileHandler)
            self.assertEqual(Path(handlers[0].baseFilename), log_path)

        self.assertIs(sys.excepthook, logging_setup._excepthook)
        self.assertIs(threading.excepthook, logging_setup._thread_excepthook)

    def test_falls_back_to_temp_directory_when_app_dir_is_unwritable(self):
        with tempfile.TemporaryDirectory() as temp_root:
            blocked = Path(temp_root) / 'blocked'
            blocked.write_text('not a directory', encoding='utf-8')
            fallback = Path(temp_root) / 'fallback'
            fallback.mkdir()

            with (
                patch.object(logging_setup, 'get_app_dir', return_value=blocked),
                patch.object(
                    logging_setup.tempfile,
                    'gettempdir',
                    return_value=str(fallback),
                ),
            ):
                logging_setup.setup_logging()

            log_path = fallback / logging_setup.LOG_FILE_NAME
            handlers = self._close_added_handlers()

            self.assertTrue(log_path.exists())
            self.assertEqual(len(handlers), 1)
            self.assertIsInstance(handlers[0], RotatingFileHandler)

    def test_uses_stream_handler_when_no_directory_is_writable(self):
        with tempfile.TemporaryDirectory() as temp_root:
            blocked = Path(temp_root) / 'blocked'
            blocked.write_text('not a directory', encoding='utf-8')

            with (
                patch.object(logging_setup, 'get_app_dir', return_value=blocked),
                patch.object(
                    logging_setup.tempfile,
                    'gettempdir',
                    return_value=str(blocked),
                ),
            ):
                logging_setup.setup_logging()

        handlers = self._added_handlers()
        self.assertEqual(len(handlers), 1)
        self.assertNotIsInstance(handlers[0], logging.FileHandler)
        self.assertIsInstance(handlers[0], logging.StreamHandler)

    def test_excepthook_logs_critical_and_delegates(self):
        logger = Mock()
        with (
            patch.object(logging_setup, 'logger', logger),
            patch.object(logging_setup.sys, '__excepthook__') as original,
        ):
            logging_setup._excepthook(ValueError, ValueError("boom"), None)

        logger.critical.assert_called_once()
        self.assertEqual(logger.critical.call_args.args[0], "未捕获异常")
        original.assert_called_once()

    def test_thread_excepthook_logs_critical_and_delegates(self):
        logger = Mock()
        args = SimpleNamespace(
            exc_value=ValueError("boom"),
            exc_type=ValueError,
            exc_traceback=None,
            thread=SimpleNamespace(name="worker"),
        )
        with (
            patch.object(logging_setup, 'logger', logger),
            patch.object(logging_setup.threading, '__excepthook__') as original,
        ):
            logging_setup._thread_excepthook(args)

        logger.critical.assert_called_once()
        self.assertEqual(logger.critical.call_args.args[0], "线程 %s 未捕获异常")
        self.assertEqual(logger.critical.call_args.args[1], "worker")
        original.assert_called_once_with(args)

    def test_thread_excepthook_ignores_missing_exception(self):
        logger = Mock()
        args = SimpleNamespace(
            exc_value=None,
            exc_type=None,
            exc_traceback=None,
            thread=None,
        )
        with (
            patch.object(logging_setup, 'logger', logger),
            patch.object(logging_setup.threading, '__excepthook__'),
        ):
            logging_setup._thread_excepthook(args)

        logger.critical.assert_not_called()

    def test_ui_log_sink_registers_once_and_forwards_levels(self):
        calls: list[str] = []
        before = len(self.root.handlers)

        logging_setup.add_ui_log_sink(calls.append)
        logging_setup.add_ui_log_sink(calls.append)

        self.assertEqual(len(self.root.handlers), before + 1)
        logging.getLogger().warning("磁盘警告")
        logging.getLogger().error("磁盘错误")

        self.assertEqual(calls, ["[警告] 磁盘警告", "[错误] 磁盘错误"])


if __name__ == '__main__':
    unittest.main()
