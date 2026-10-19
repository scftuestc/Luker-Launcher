"""Luker 与 GCL 子进程的启动、停止和日志读取。"""

import contextlib
import socket
import subprocess
import time
from collections.abc import Callable, Sequence
from pathlib import Path
from threading import RLock, Thread, current_thread

import psutil

from win_job import assign_to_job

# 单次读取上限，避免子进程输出超长行时无限占用内存
MAX_LOG_CHUNK = 64 * 1024


class _ProcessManagerBase:
    """子进程生命周期的公共实现；子类只负责校验目标并构建启动命令。"""

    name = "进程"
    # GCL 的日志标签形如 [GCL 信息]，Luker 保持 [信息]
    log_scope = ""

    def __init__(self, target: Path, encoding: str = "utf-8") -> None:
        self.target = target
        self._encoding = encoding
        self.process: subprocess.Popen[str] | None = None
        self._log_thread: Thread | None = None
        self._running = False
        self._op_lock = RLock()  # 串行化 start/stop/restart，避免并发操作同一进程
        self._log_callbacks: list[Callable[[str], None]] = []

    def _tag(self, level: str) -> str:
        """生成 [信息] 或 [GCL 错误] 形式的日志前缀。"""
        scope = f"{self.log_scope} " if self.log_scope else ""
        return f"[{scope}{level}]"

    def _startup_error(self) -> str | None:
        """启动前校验，返回错误信息；返回 None 表示可以启动。"""
        return None

    def _pre_start_error(self) -> str | None:
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

    def _emit_log(self, line: str) -> None:
        for callback in self._log_callbacks:
            with contextlib.suppress(Exception):
                callback(line)

    def _read_output(self, process: subprocess.Popen[str]) -> None:
        """持续读取指定进程的输出，直到进程退出或收到停止请求。"""
        stdout = process.stdout
        if stdout is None:
            return

        try:
            while self._running:
                line = stdout.readline(MAX_LOG_CHUNK)
                if not line:
                    break
                self._emit_log(line.rstrip('\n\r'))
        except (OSError, ValueError) as e:
            self._emit_log(f"{self._tag('错误')} 读取输出失败: {e}")
        finally:
            with contextlib.suppress(OSError):
                stdout.close()

    def _close_process_pipes(self, process: subprocess.Popen[str]) -> None:
        for stream in (process.stdin, process.stdout):
            if stream is not None:
                with contextlib.suppress(OSError, ValueError):
                    stream.close()

    def _join_log_thread(self) -> None:
        thread = self._log_thread
        if thread and thread.is_alive() and thread is not current_thread():
            thread.join(timeout=1)
        self._log_thread = None

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

    def _kill_process_tree(self, pid: int) -> bool:
        """先终止子进程树，再终止父进程；返回是否确认全部退出。"""
        try:
            parent = psutil.Process(pid)
        except psutil.NoSuchProcess:
            return True
        except Exception as e:
            self._emit_log(f"{self._tag('警告')} 无法访问进程树: {e}")
            return False

        tree_ok = True
        try:
            children = parent.children(recursive=True)
        except psutil.NoSuchProcess:
            children = []
        except Exception as e:
            self._emit_log(f"{self._tag('警告')} 枚举子进程失败: {e}")
            children = []
            tree_ok = False

        for child in children:
            try:
                child.terminate()
            except psutil.NoSuchProcess:
                pass
            except Exception as e:
                self._emit_log(f"{self._tag('警告')} 终止子进程失败: {e}")
                tree_ok = False

        try:
            _, alive = psutil.wait_procs(children, timeout=3)
        except Exception as e:
            self._emit_log(f"{self._tag('警告')} 等待子进程退出失败: {e}")
            alive = []
            tree_ok = False

        for child in alive:
            try:
                child.kill()
            except psutil.NoSuchProcess:
                pass
            except Exception as e:
                self._emit_log(f"{self._tag('警告')} 强制结束子进程失败: {e}")
                tree_ok = False

        if alive:
            _, still_alive = psutil.wait_procs(alive, timeout=2)
            if still_alive:
                self._emit_log(f"{self._tag('警告')} 仍有 {len(still_alive)} 个子进程未退出")
                tree_ok = False

        try:
            parent.terminate()
            parent.wait(timeout=3)
        except psutil.TimeoutExpired:
            try:
                parent.kill()
                parent.wait(timeout=3)
            except psutil.TimeoutExpired:
                self._emit_log(f"{self._tag('警告')} 父进程未能退出")
                tree_ok = False
            except psutil.NoSuchProcess:
                pass
        except psutil.NoSuchProcess:
            pass
        except Exception as e:
            self._emit_log(f"{self._tag('警告')} 终止父进程失败: {e}")
            tree_ok = False

        return tree_ok

    def stop(self) -> bool:
        with self._op_lock:
            process = self.process
            if process is None or process.poll() is not None:
                self._running = False
                self.process = None
                if process is not None:
                    self._close_process_pipes(process)
                self._join_log_thread()
                self._emit_log(f"{self._tag('信息')} {self.name} 未在运行")
                return True

            try:
                self._running = False
                self._emit_log(
                    f"{self._tag('信息')} 正在停止 {self.name} 进程 (PID: {process.pid})..."
                )
                tree_ok = self._kill_process_tree(process.pid)

                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill()
                    try:
                        process.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        tree_ok = False

                # 关闭管道可唤醒仍阻塞在 readline 的读取线程
                self._close_process_pipes(process)
                self._join_log_thread()

                if process.poll() is None:
                    # 父进程仍存活时保留引用，用户可以再次尝试停止
                    tree_ok = False
                    self._emit_log(f"{self._tag('警告')} {self.name} 父进程仍未退出")
                else:
                    self.process = None

                if tree_ok:
                    self._emit_log(f"{self._tag('信息')} {self.name} 已停止")
                    return True

                self._emit_log(f"{self._tag('警告')} {self.name} 停止后仍有子进程可能存活")
                return False

            except Exception as e:
                self._emit_log(f"{self._tag('错误')} 停止失败: {e}")
                self._close_process_pipes(process)
                self._join_log_thread()
                if process.poll() is not None:
                    self.process = None
                return False

    def restart(self) -> bool:
        with self._op_lock:
            self._emit_log(f"{self._tag('信息')} 正在重启 {self.name}...")
            if not self.stop():
                self._emit_log(f"{self._tag('错误')} 停止失败，取消重启")
                return False
            time.sleep(1)
            return self.start()


class LukerProcessManager(_ProcessManagerBase):
    """管理 Luker（node server.js）子进程。"""

    name = "Luker"

    def __init__(
        self,
        luker_path: str,
        let_luker_open_browser: bool = True,
        server_port: int | None = None,
    ) -> None:
        super().__init__(Path(luker_path), encoding="utf-8")
        self.luker_path = self.target
        # 为 False 时向 Luker 传 --browserLaunchEnabled false，
        # 由启动器自己打开 PWA，避免弹出两个浏览器窗口
        self.let_luker_open_browser = let_luker_open_browser
        self.server_port = server_port

    def _startup_error(self) -> str | None:
        server_js = self.luker_path / "server.js"
        if not server_js.exists():
            return f"未找到 server.js: {server_js}"
        return None

    def _pre_start_error(self) -> str | None:
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

    def _startup_error(self) -> str | None:
        if not self.bat_path.exists():
            return f"未找到 bat 文件: {self.bat_path}"
        return None

    def _build_command(self) -> Sequence[str]:
        return ["cmd", "/c", str(self.bat_path)]

    def _startup_cwd(self) -> str:
        return str(self.bat_path.parent)
