#include <sourcemod>
#include <socket>

#define UDP_HOST "127.0.0.1"
#define UDP_PORT 45678

Socket g_socket;

public Plugin myinfo = {
    name = "L4D2 Hurt -> DGHub",
    author = "yufun",
    description = "Send player_hurt damage/type via UDP",
    version = "1.0",
    url = ""
};

public void OnPluginStart() {
    g_socket = new Socket(SOCKET_UDP);
    if (g_socket == null) {
        SetFailState("SocketCreate failed");
    }

    g_socket.Bind("127.0.0.1", 0);

    HookEvent("player_hurt", Event_PlayerHurt);
}

public void Event_PlayerHurt(Event event, const char[] name, bool dontBroadcast) {
    int victim = GetClientOfUserId(event.GetInt("userid"));
    int damage = event.GetInt("dmg_health");
    int type   = event.GetInt("type");

    if (victim <= 0 || damage <= 0)
        return;

    char payload[32];
    Format(payload, sizeof(payload), "%d|%d", damage, type);

    g_socket.SendTo(payload, -1, UDP_HOST, UDP_PORT);
}