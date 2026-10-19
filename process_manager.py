"""Luker 与 GCL 子进程的启动、停止和日志读取。"""

import socket
import subprocess
import time
from pathlib import Path
from threading import RLock, Thread
from typing import Callable, List, Optional, Sequence

import psutil

from win_job import assign_to_job


class _ProcessManagerBase:
    """子进程生命周期的公共实现；子类只负责校验目标并构建启动命令。"""

    name = "进程"
    # GCL 的日志标签形如 [GCL 信息]，Luker 保持 [信息]
    log_scope = ""

    def __init__(self, target: Path, encoding: str = "utf-8") -> None:
        self.target = target
        self._encoding = encoding
        self.process: Optional[subprocess.Popen] = None
        self._log_thread: Optional[Thread] = None
        self._running = False
        self._op_lock = RLock()  # 串行化 start/stop/restart，避免并发操作同一进程
        self._log_callbacks: List[Callable[[str], None]] = []

    def _tag(self, level: str) -> str:
        """生成 [信息] 或 [GCL 错误] 形式的日志前缀。"""
        scope = f"{self.log_scope} " if self.log_scope else ""
        return f"[{scope}{level}]"

    def _startup_error(self) -> Optional[str]:
        """启动前校验，返回错误信息；返回 None 表示可以启动。"""
        return None

    def _pre_start_error(self) -> Optional[str]:
        """目标文件检查通过后的额外检查，例如端口是否已被占用。"""
        return None

    def _build_command(self) -> Sequence[str]:
        """返回启动命令参数列表。"""
        raise NotImplementedError

    def _startup_cwd(self) -> str:
        return str(self.target)

    @property
    def is_running(self) -> bool:
        process = self.process
        return process is not None and process.poll() is None

    def add_log_callback(self, callback: Callable[[str], None]) -> None:
        self._log_callbacks.append(callback)

    def remove_log_callback(self, callback: Callable[[str], None]) -> None:
        if callback in self._log_callbacks:
            self._log_callbacks.remove(callback)

    def _emit_log(self, line: str) -> None:
        for callback in self._log_callbacks:
            try:
                callback(line)
            except Exception:
                pass

    def _read_output(self, process: subprocess.Popen) -> None:
        """持续读取指定进程的输出，直到进程退出或收到停止请求。"""
        stdout = process.stdout
        if stdout is None:
            return

        try:
            for line in iter(stdout.readline, ''):
                if not self._running:
                    break
                if line:
                    self._emit_log(line.rstrip('\n\r'))
        except (OSError, ValueError) as e:
            self._emit_log(f"{self._tag('错误')} 读取输出失败: {e}")
        finally:
            try:
                stdout.close()
            except OSError:
                pass

    def start(self) -> bool:
        with self._op_lock:
            if self.is_running:
                self._emit_log(f"{self._tag('信息')} {self.name} 已经在运行中")
                return True

            error = self._startup_error() or self._pre_start_error()
            if error:
                self._emit_log(f"{self._tag('错误')} {error}")
                return False

            try:
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = subprocess.SW_HIDE

                process = subprocess.Popen(
                    self._build_command(),
                    cwd=self._startup_cwd(),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    stdin=subprocess.PIPE,
                    text=True,
                    bufsize=1,
                    startupinfo=startupinfo,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                    encoding=self._encoding,
                    errors='replace',
                )

                # 强制结束启动器时由 Job Object 兜底清理子进程
                if not assign_to_job(process):
                    self._emit_log(
                        f"{self._tag('警告')} 无法将子进程加入 Job Object，"
                        f"强制退出时可能留下孤儿进程"
                    )

                self.process = process
                self._running = True
                self._log_thread = Thread(
                    target=self._read_output,
                    args=(process,),
                    daemon=True,
                    name=f"{type(self).__name__}LogReader",
                )
                self._log_thread.start()

                self._emit_log(f"{self._tag('信息')} {self.name} 启动中...")
                return True

            except (OSError, ValueError) as e:
                self._emit_log(f"{self._tag('错误')} 启动失败: {e}")
                return False

    def _kill_process_tree(self, pid: int) -> None:
        """先终止子进程树，再终止父进程，避免留下孤儿进程。"""
        try:
            parent = psutil.Process(pid)
            children = parent.children(recursive=True)

            for child in children:
                try:
                    child.terminate()
                except psutil.NoSuchProcess:
                    pass

            _, alive = psutil.wait_procs(children, timeout=3)

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
            self._emit_log(f"{self._tag('警告')} 杀死进程树时出错: {e}")

    def stop(self) -> bool:
        with self._op_lock:
            process = self.process
            if process is None or process.poll() is not None:
                self._running = False
                self.process = None
                self._emit_log(f"{self._tag('信息')} {self.name} 未在运行")
                return True

            try:
                self._running = False
                self._emit_log(
                    f"{self._tag('信息')} 正在停止 {self.name} 进程 (PID: {process.pid})..."
                )
                self._kill_process_tree(process.pid)

                # 回收 Popen 句柄；进程树已终止，这里通常立即返回
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill()

                self.process = None
                self._emit_log(f"{self._tag('信息')} {self.name} 已停止")
                return True

            except Exception as e:
                self._emit_log(f"{self._tag('错误')} 停止失败: {e}")
                return False

    def restart(self) -> bool:
        with self._op_lock:
            self._emit_log(f"{self._tag('信息')} 正在重启 {self.name}...")
            self.stop()
            time.sleep(1)
            return self.start()


class ProcessManager(_ProcessManagerBase):
    """管理 Luker（node server.js）子进程。"""

    name = "Luker"

    def __init__(
        self,
        luker_path: str,
        let_luker_open_browser: bool = True,
        server_port: Optional[int] = None,
    ) -> None:
        super().__init__(Path(luker_path), encoding="utf-8")
        self.luker_path = self.target
        # 为 False 时向 Luker 传 --browserLaunchEnabled false，
        # 由启动器自己打开 PWA，避免弹出两个浏览器窗口
        self.let_luker_open_browser = let_luker_open_browser
        self.server_port = server_port

    def _startup_error(self) -> Optional[str]:
        server_js = self.luker_path / "server.js"
        if not server_js.exists():
            return f"未找到 server.js: {server_js}"
        return None

    def _pre_start_error(self) -> Optional[str]:
        """端口被占用时阻止重复启动。"""
        if self.server_port and self._is_port_in_use(self.server_port):
            return f"端口 {self.server_port} 已被占用，可能已有 Luker 在运行；请先关闭它再启动"
        return None

    @staticmethod
    def _is_port_in_use(port: int) -> bool:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                return True
        except OSError:
            return False

    def _build_command(self) -> Sequence[str]:
        # 直接使用 node server.js，而不是通过 Start.bat，
        # 这样可以传递 --browserLaunchEnabled 参数来控制是否自动打开浏览器
        cmd = ["node", "server.js"]
        if not self.let_luker_open_browser:
            cmd.extend(["--browserLaunchEnabled", "false"])
        return cmd


class GCLProcessManager(_ProcessManagerBase):
    """管理 GCL 的 start.bat 子进程。"""

    name = "GCL"
    log_scope = "GCL"

    def __init__(self, bat_path: str) -> None:
        # bat 的输出由 cmd 按系统 ANSI 代码页编码（中文系统为 CP936），
        # 不能用 utf-8 解码，否则中文日志会变成乱码
        super().__init__(Path(bat_path), encoding="mbcs")
        self.bat_path = self.target

    def _startup_error(self) -> Optional[str]:
        if not self.bat_path.exists():
            return f"未找到 bat 文件: {self.bat_path}"
        return None

    def _build_command(self) -> Sequence[str]:
        return ["cmd", "/c", str(self.bat_path)]

    def _startup_cwd(self) -> str:
        return str(self.bat_path.parent)
