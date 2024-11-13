import asyncio
import json
import random
import time
import uuid
from pathlib import Path
from typing import Set, Tuple

import aiohttp
from loguru import logger
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler


class ProxyFileHandler(FileSystemEventHandler):
    def __init__(self, callback):
        self.callback = callback
        self._last_modified = 0

    def on_modified(self, event):
        current_time = time.time()
        if current_time - self._last_modified > 0.5:  # 500ms debounce
            self._last_modified = current_time
            if event.src_path.endswith("proxy.txt"):
                self.callback()


class ProxyManager:
    def __init__(self, user_id, loop):
        self.user_id = user_id
        self.tasks = {}
        self.proxy_list = set()
        self.proxy_path = Path("proxy.txt")
        self.loop = loop  # Store the main event loop
        self.load_proxies()

    def load_proxies(self) -> Tuple[Set[str], Set[str]]:
        try:
            if not self.proxy_path.exists():
                logger.error("File proxy.txt does not exist!")
                return set(), set()

            with open(self.proxy_path, "r") as f:
                new_proxies = set()
                for line in f:
                    proxy = line.strip()
                    if proxy:  # Skip empty lines
                        # Ensure consistent format with http:// or socks5:// prefix
                        if not proxy.startswith(("http://", "socks5://")):
                            proxy = f"http://{proxy}"
                        new_proxies.add(proxy)

            if not new_proxies:
                logger.warning("No proxies found in proxy.txt!")

            added_proxies = new_proxies - self.proxy_list
            removed_proxies = self.proxy_list - new_proxies

            if added_proxies:
                logger.info(f"Added proxies: {added_proxies}.")
            if removed_proxies:
                logger.info(f"Removed proxies: {removed_proxies}.")

            self.proxy_list = new_proxies
            return added_proxies, removed_proxies

        except Exception as e:
            logger.error(f"Error loading proxies: {e}.")
            return set(), set()

    def handle_file_change(self):
        logger.info("Detected change in proxy.txt.")
        added_proxies, removed_proxies = self.load_proxies()
        if added_proxies or removed_proxies:
            asyncio.run_coroutine_threadsafe(self.update_tasks(added_proxies, removed_proxies), self.loop)

    async def update_tasks(self, added_proxies, removed_proxies):
        for proxy in removed_proxies:
            if proxy in self.tasks:
                logger.info(f"Cancelling task for removed proxy: {proxy}.")
                self.tasks[proxy].cancel()
                await asyncio.sleep(0)
                del self.tasks[proxy]

        for proxy in added_proxies:
            if proxy not in self.tasks:
                logger.info(f"Starting new task for proxy: {proxy}.")
                task = asyncio.create_task(connect_to_wss(proxy, self.user_id))
                self.tasks[proxy] = task


async def connect_to_wss(socks5_proxy, user_id):
    device_id = str(uuid.uuid3(uuid.NAMESPACE_DNS, socks5_proxy))
    logger.info(f"Connecting with proxy {socks5_proxy}, device ID: {device_id}.")

    # Convert http:// to socks5:// for the actual connection
    proxy_url = socks5_proxy.replace("http://", "socks5://")
    uri = "wss://proxy.wynd.network:4650/"
    custom_headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"}

    async with aiohttp.ClientSession() as session:
        while True:
            try:
                await asyncio.sleep(random.randint(1, 10) / 10)

                async with session.ws_connect(uri, proxy=proxy_url, ssl=False, headers=custom_headers) as websocket:
                    logger.info(f"Successfully connected to WebSocket using proxy: {socks5_proxy}.")

                    async def send_ping():
                        while True:
                            try:
                                send_message = json.dumps(
                                    {
                                        "id": str(uuid.uuid4()),
                                        "version": "1.0.0",
                                        "action": "PING",
                                        "data": {},
                                    }
                                )
                                logger.debug(f"Ping response: {send_message}.")
                                await websocket.send_str(send_message)
                                await asyncio.sleep(20)
                            except Exception as e:
                                logger.error(f"Error in ping task: {e}.")
                                break

                    ping_task = asyncio.create_task(send_ping())

                    try:
                        async for response in websocket:
                            if response.type == aiohttp.WSMsgType.TEXT:
                                message = json.loads(response.data)
                                logger.info(f"Received message: {message}.")

                                if message.get("action") == "AUTH":
                                    auth_response = {
                                        "id": message["id"],
                                        "origin_action": "AUTH",
                                        "result": {
                                            "browser_id": device_id,
                                            "user_id": user_id,
                                            "user_agent": custom_headers["User-Agent"],
                                            "timestamp": int(time.time()),
                                            "device_type": "extension",
                                            "version": "2.5.0",
                                        },
                                    }
                                    logger.debug(f"Auth response: {auth_response}.")
                                    await websocket.send_str(json.dumps(auth_response))

                                elif message.get("action") == "PONG":
                                    pong_response = {
                                        "id": message["id"],
                                        "origin_action": "PONG",
                                    }
                                    logger.debug(f"Pong response: {pong_response}.")
                                    await websocket.send_str(json.dumps(pong_response))

                            elif response.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR,):
                                logger.warning(f"WebSocket connection closed or error occurred: {response.data}.")
                                break
                    finally:
                        ping_task.cancel()

            except asyncio.CancelledError:
                logger.info(f"Task cancelled for proxy: {socks5_proxy}.")
                return
            except Exception as e:
                logger.error(f"Error in WebSocket connection: {e}.")
                logger.error(f"Proxy used: {socks5_proxy}.")
                await asyncio.sleep(5)


async def main():
    try:
        with open("id.txt", "r") as f:
            user_id = f.readline().strip()
            if not user_id:
                raise ValueError("File id.txt is empty!")
    except Exception as e:
        logger.error(f"Error reading id.txt: {e}.")
        return

    # Initialize proxy manager with event loop
    loop = asyncio.get_running_loop()
    proxy_manager = ProxyManager(user_id, loop)
    
    # Set up file watching
    event_handler = ProxyFileHandler(proxy_manager.handle_file_change)
    observer = Observer()
    observer.schedule(event_handler, path=str(Path("proxy.txt").parent), recursive=False)
    observer.start()
    logger.info("Started file observer for proxy.txt.")

    try:
        # Start initial tasks
        for proxy in proxy_manager.proxy_list:
            task = asyncio.create_task(connect_to_wss(proxy, user_id))
            proxy_manager.tasks[proxy] = task

        # Keep the main task running
        while True:
            await asyncio.sleep(1)

    except asyncio.CancelledError:
        logger.info("Main task cancelled.")
    except Exception as e:
        logger.error(f"Error in main task: {e}.")
    finally:
        logger.info("Shutting down.")
        observer.stop()
        observer.join()
        for task in proxy_manager.tasks.values():
            task.cancel()

if __name__ == "__main__":
    asyncio.run(main())
