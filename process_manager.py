import subprocess
import os
import signal
import time
from pathlib import Path
from typing import Optional, Callable, List
from threading import Thread
import queue
import psutil


class ProcessManager:
    def __init__(self, luker_path: str, autorun: bool = True):
        self.luker_path = Path(luker_path)
        self.autorun = autorun  # 是否让 Luker 自动打开浏览器
        self.process: Optional[subprocess.Popen] = None
        self.log_queue: queue.Queue = queue.Queue()
        self._log_thread: Optional[Thread] = None
        self._running = False

        self._log_callbacks: List[Callable[[str], None]] = []

    @property
    def is_running(self) -> bool:
        if self.process is None:
            return False
        return self.process.poll() is None

    def add_log_callback(self, callback: Callable[[str], None]) -> None:
        self._log_callbacks.append(callback)

    def remove_log_callback(self, callback: Callable[[str], None]) -> None:
        if callback in self._log_callbacks:
            self._log_callbacks.remove(callback)

    def _emit_log(self, line: str) -> None:
        self.log_queue.put(line)
        for callback in self._log_callbacks:
            try:
                callback(line)
            except Exception:
                pass

    def _read_output(self) -> None:
        if self.process is None:
            return

        try:
            for line in iter(self.process.stdout.readline, ''):
                if not self._running:
                    break
                if line:
                    self._emit_log(line.rstrip('\n\r'))
        except Exception as e:
            self._emit_log(f"[错误] 读取输出失败: {e}")

    def start(self) -> bool:
        if self.is_running:
            self._emit_log("[信息] Luker 已经在运行中")
            return True

        server_js = self.luker_path / "server.js"
        if not server_js.exists():
            self._emit_log(f"[错误] 未找到 server.js: {server_js}")
            return False

        try:
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE

            # 构建启动命令
            # 直接使用 node server.js，而不是通过 Start.bat
            # 这样可以传递 --browserLaunchEnabled 参数来控制是否自动打开浏览器
            cmd = ["node", "server.js"]
            if not self.autorun:
                cmd.append("--browserLaunchEnabled")
                cmd.append("false")

            self.process = subprocess.Popen(
                cmd,
                cwd=str(self.luker_path),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                stdin=subprocess.PIPE,
                text=True,
                bufsize=1,
                startupinfo=startupinfo,
                creationflags=subprocess.CREATE_NO_WINDOW,
                encoding='utf-8',
                errors='replace'
            )

            self._running = True
            self._log_thread = Thread(target=self._read_output, daemon=True)
            self._log_thread.start()

            self._emit_log("[信息] Luker 启动中...")
            return True

        except Exception as e:
            self._emit_log(f"[错误] 启动失败: {e}")
            return False

    def _kill_process_tree(self, pid: int) -> None:
        try:
            parent = psutil.Process(pid)
            children = parent.children(recursive=True)

            for child in children:
                try:
                    child.terminate()
                except psutil.NoSuchProcess:
                    pass

            gone, alive = psutil.wait_procs(children, timeout=3)

            for p in alive:
                try:
                    p.kill()
                except psutil.NoSuchProcess:
                    pass

            try:
                parent.terminate()
                parent.wait(timeout=3)
            except psutil.TimeoutExpired:
                parent.kill()
            except psutil.NoSuchProcess:
                pass

        except psutil.NoSuchProcess:
            pass
        except Exception as e:
            self._emit_log(f"[警告] 杀死进程树时出错: {e}")

    def stop(self) -> bool:
        if not self.is_running:
            self._emit_log("[信息] Luker 未在运行")
            return True

        try:
            self._running = False

            if self.process:
                pid = self.process.pid
                self._emit_log(f"[信息] 正在停止 Luker 进程 (PID: {pid})...")
                self._kill_process_tree(pid)

            self._emit_log("[信息] Luker 已停止")
            self.process = None
            return True

        except Exception as e:
            self._emit_log(f"[错误] 停止失败: {e}")
            return False

    def restart(self) -> bool:
        self._emit_log("[信息] 正在重启 Luker...")
        self.stop()
        time.sleep(1)
        return self.start()

    def get_recent_logs(self, count: int = 100) -> List[str]:
        logs = []
        while not self.log_queue.empty() and len(logs) < count:
            try:
                logs.append(self.log_queue.get_nowait())
            except queue.Empty:
                break
        return logs


class GCLProcessManager:
    """GCL 进程管理器，用于管理 GCL 的 start.bat 进程"""

    def __init__(self, bat_path: str):
        self.bat_path = Path(bat_path)
        self.process: Optional[subprocess.Popen] = None
        self.log_queue: queue.Queue = queue.Queue()
        self._log_thread: Optional[Thread] = None
        self._running = False

        self._log_callbacks: List[Callable[[str], None]] = []

    @property
    def is_running(self) -> bool:
        if self.process is None:
            return False
        return self.process.poll() is None

    def add_log_callback(self, callback: Callable[[str], None]) -> None:
        self._log_callbacks.append(callback)

    def remove_log_callback(self, callback: Callable[[str], None]) -> None:
        if callback in self._log_callbacks:
            self._log_callbacks.remove(callback)

    def _emit_log(self, line: str) -> None:
        self.log_queue.put(line)
        for callback in self._log_callbacks:
            try:
                callback(line)
            except Exception:
                pass

    def _read_output(self) -> None:
        if self.process is None:
            return

        try:
            for line in iter(self.process.stdout.readline, ''):
                if not self._running:
                    break
                if line:
                    self._emit_log(line.rstrip('\n\r'))
        except Exception as e:
            self._emit_log(f"[GCL 错误] 读取输出失败: {e}")

    def start(self) -> bool:
        if self.is_running:
            self._emit_log("[GCL 信息] GCL 已经在运行中")
            return True

        if not self.bat_path.exists():
            self._emit_log(f"[GCL 错误] 未找到 bat 文件: {self.bat_path}")
            return False

        try:
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE

            # 使用 cmd /c 来运行 bat 文件
            self.process = subprocess.Popen(
                ["cmd", "/c", str(self.bat_path)],
                cwd=str(self.bat_path.parent),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                stdin=subprocess.PIPE,
                text=True,
                bufsize=1,
                startupinfo=startupinfo,
                creationflags=subprocess.CREATE_NO_WINDOW,
                encoding='utf-8',
                errors='replace'
            )

            self._running = True
            self._log_thread = Thread(target=self._read_output, daemon=True)
            self._log_thread.start()

            self._emit_log("[GCL 信息] GCL 启动中...")
            return True

        except Exception as e:
            self._emit_log(f"[GCL 错误] 启动失败: {e}")
            return False

    def _kill_process_tree(self, pid: int) -> None:
        try:
            parent = psutil.Process(pid)
            children = parent.children(recursive=True)

            for child in children:
                try:
                    child.terminate()
                except psutil.NoSuchProcess:
                    pass

            gone, alive = psutil.wait_procs(children, timeout=3)

            for p in alive:
                try:
                    p.kill()
                except psutil.NoSuchProcess:
                    pass

            try:
                parent.terminate()
                parent.wait(timeout=3)
            except psutil.TimeoutExpired:
                parent.kill()
            except psutil.NoSuchProcess:
                pass

        except psutil.NoSuchProcess:
            pass
        except Exception as e:
            self._emit_log(f"[GCL 警告] 杀死进程树时出错: {e}")

    def stop(self) -> bool:
        if not self.is_running:
            self._emit_log("[GCL 信息] GCL 未在运行")
            return True

        try:
            self._running = False

            if self.process:
                pid = self.process.pid
                self._emit_log(f"[GCL 信息] 正在停止 GCL 进程 (PID: {pid})...")
                self._kill_process_tree(pid)

            self._emit_log("[GCL 信息] GCL 已停止")
            self.process = None
            return True

        except Exception as e:
            self._emit_log(f"[GCL 错误] 停止失败: {e}")
            return False

    def restart(self) -> bool:
        self._emit_log("[GCL 信息] 正在重启 GCL...")
        self.stop()
        time.sleep(1)
        return self.start()

    def get_recent_logs(self, count: int = 100) -> List[str]:
        logs = []
        while not self.log_queue.empty() and len(logs) < count:
            try:
                logs.append(self.log_queue.get_nowait())
            except queue.Empty:
                break
        return logs
