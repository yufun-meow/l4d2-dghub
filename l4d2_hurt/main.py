import asyncio
import json
import os
import websockets

UDP_HOST = "127.0.0.1"
UDP_PORT = 45678

# 伤害类型位 → config 里的 preset 键名
TYPE_TO_KEY = [
    (1048576, "preset_acid"),    # DMG_ACID
    (8,       "preset_burn"),    # DMG_BURN
    (64,      "preset_blast"),   # DMG_BLAST
    (32,      "preset_fall"),    # DMG_FALL
    (128,     "preset_club"),    # DMG_CLUB
    (2,       "preset_bullet"),  # DMG_BULLET
]

DEFAULT_CONFIG = {
    "delta_multiplier": 2.0,
    "delta_max": 70,
    "duration_s": 1.0,
    "preset_default": "",
    "preset_burn": "",
    "preset_blast": "",
    "preset_fall": "",
    "preset_club": "",
    "preset_bullet": "",
    "preset_acid": "",
    "channel": "both",
}


class Plugin:
    def __init__(self, ws):
        self.ws = ws
        self.config = dict(DEFAULT_CONFIG)

    def apply_config(self, data: dict):
        self.config.update(data)

    def pick_preset(self, dtype: int) -> str:
        for bit, key in TYPE_TO_KEY:
            if dtype & bit:
                return self.config.get(key, "") or self.config.get("preset_default", "")
        return self.config.get("preset_default", "")

    def calc_delta(self, dmg: int) -> int:
        mult = float(self.config["delta_multiplier"])
        cap = int(self.config["delta_max"])
        return int(min(dmg * mult, cap))

    async def on_udp(self, dmg: int, dtype: int):
        preset = self.pick_preset(dtype)
        delta = self.calc_delta(dmg)
        duration = float(self.config["duration_s"])
        channel = self.config["channel"]

        if preset:
            msg = {
                "op": "trigger",
                "action": "both",
                "delta_pct": delta,
                "strength_mode": "rollback",
                "duration_s": duration,
                "preset": preset,
                "channel": channel,
                "label": f"L4D2 -{dmg}HP ({preset})",
            }
        else:
            msg = {
                "op": "trigger",
                "action": "strength",
                "delta_pct": delta,
                "strength_mode": "rollback",
                "duration_s": duration,
                "channel": channel,
                "label": f"L4D2 -{dmg}HP",
            }

        try:
            await self.ws.send(json.dumps(msg))
        except Exception:
            pass


class UdpReceiver(asyncio.DatagramProtocol):
    def __init__(self, plugin: Plugin):
        self.plugin = plugin

    def datagram_received(self, data, addr):
        try:
            dmg_s, type_s = data.decode().strip().split("|")
            dmg = int(dmg_s)
            dtype = int(type_s)
        except Exception:
            return
        asyncio.create_task(self.plugin.on_udp(dmg, dtype))


async def main():
    host = os.environ["DGHUB_HOST"]
    port = os.environ["DGHUB_PORT"]
    token = os.environ["DGHUB_TOKEN"]

    async with websockets.connect(
        f"ws://{host}:{port}/ws/plugin?token={token}"
    ) as ws:
        await ws.send(json.dumps({
            "op": "hello",
            "token": token,
            "manifest": {
                "id": "l4d2_hurt",
                "name": "L4D2 受伤",
                "version": "0.1.0",
                "sdk": "1",
            },
        }))
        ack = json.loads(await ws.recv())
        if not ack.get("accepted"):
            print("handshake rejected:", ack.get("reason"))
            return

        plugin = Plugin(ws)

        loop = asyncio.get_running_loop()
        await loop.create_datagram_endpoint(
            lambda: UdpReceiver(plugin),
            local_addr=(UDP_HOST, UDP_PORT),
        )

        async for raw in ws:
            try:
                msg = json.loads(raw)
            except Exception:
                continue
            op = msg.get("op")
            if op == "config":
                plugin.apply_config(msg.get("data", {}))
            elif op == "config_changed":
                key = msg.get("key")
                value = msg.get("value")
                plugin.config[key] = value
            elif op == "stop":
                return


if __name__ == "__main__":
    asyncio.run(main())