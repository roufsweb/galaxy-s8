/*
 * s8_usb_agentd.c -- Zero-Config Universal USB RWP Control & Dual-Env PTY Agent
 *
 * Runs persistently inside the Galaxy S8 AP ramdisk namespace (:7860, reached via
 * `adb forward tcp:<port> tcp:7860` or USB RNDIS 192.168.7.2:7860).
 *
 * Provides OS-agnostic hardware telemetry, command execution, and RFC 6455
 * WebSocket interactive PTY shells for both:
 *   - env=ap : The AP phone base (/sbin/sh)
 *   - env=os : Any mounted/running guest Linux rootfs (/mnt/rootfs or /mnt/ubuntu)
 *              via PID 1 nsenter (systemd/OpenRC) or chroot fallback (any untested OS).
 */

#define _GNU_SOURCE
#include <arpa/inet.h>
#include <ctype.h>
#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <net/if.h>
#include <netinet/in.h>
#include <poll.h>
#include <pty.h>
#include <signal.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/socket.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <sys/utsname.h>
#include <sys/wait.h>
#include <termios.h>
#include <unistd.h>

#define AGENT_PORT 7860
#define MAX_REQ_BUF 65536
#define MAX_CMD_OUT 131072
#define WS_GUID "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"

/* ---------- Minimal SHA-1 & Base64 for RFC 6455 WebSocket Handshake ---------- */

typedef struct {
    uint32_t state[5];
    uint64_t count;
    uint8_t buffer[64];
} sha1_ctx_t;

static uint32_t rotl32(uint32_t x, int n) {
    return (x << n) | (x >> (32 - n));
}

static void sha1_transform(uint32_t state[5], const uint8_t block[64]) {
    uint32_t w[80];
    for (int i = 0; i < 16; i++) {
        w[i] = ((uint32_t)block[i * 4] << 24) |
               ((uint32_t)block[i * 4 + 1] << 16) |
               ((uint32_t)block[i * 4 + 2] << 8) |
               ((uint32_t)block[i * 4 + 3]);
    }
    for (int i = 16; i < 80; i++) {
        w[i] = rotl32(w[i - 3] ^ w[i - 8] ^ w[i - 14] ^ w[i - 16], 1);
    }
    uint32_t a = state[0], b = state[1], c = state[2], d = state[3], e = state[4];
    for (int i = 0; i < 80; i++) {
        uint32_t f, k;
        if (i < 20) {
            f = (b & c) | ((~b) & d);
            k = 0x5A827999U;
        } else if (i < 40) {
            f = b ^ c ^ d;
            k = 0x6ED9EBA1U;
        } else if (i < 60) {
            f = (b & c) | (b & d) | (c & d);
            k = 0x8F1BBCDCU;
        } else {
            f = b ^ c ^ d;
            k = 0xCA62C1D6U;
        }
        uint32_t tmp = rotl32(a, 5) + f + e + k + w[i];
        e = d;
        d = c;
        c = rotl32(b, 30);
        b = a;
        a = tmp;
    }
    state[0] += a;
    state[1] += b;
    state[2] += c;
    state[3] += d;
    state[4] += e;
}

static void sha1_digest(const uint8_t *data, size_t len, uint8_t out[20]) {
    sha1_ctx_t ctx;
    ctx.state[0] = 0x67452301U;
    ctx.state[1] = 0xEFCDAB89U;
    ctx.state[2] = 0x98BADCFEU;
    ctx.state[3] = 0x10325476U;
    ctx.state[4] = 0xC3D2E1F0U;
    ctx.count = 0;

    size_t idx = 0;
    for (size_t i = 0; i < len; i++) {
        ctx.buffer[idx++] = data[i];
        ctx.count += 8;
        if (idx == 64) {
            sha1_transform(ctx.state, ctx.buffer);
            idx = 0;
        }
    }
    ctx.buffer[idx++] = 0x80;
    if (idx > 56) {
        while (idx < 64) ctx.buffer[idx++] = 0;
        sha1_transform(ctx.state, ctx.buffer);
        idx = 0;
    }
    while (idx < 56) ctx.buffer[idx++] = 0;
    for (int i = 0; i < 8; i++) {
        ctx.buffer[56 + i] = (uint8_t)((ctx.count >> ((7 - i) * 8)) & 0xFF);
    }
    sha1_transform(ctx.state, ctx.buffer);
    for (int i = 0; i < 5; i++) {
        out[i * 4] = (uint8_t)(ctx.state[i] >> 24);
        out[i * 4 + 1] = (uint8_t)(ctx.state[i] >> 16);
        out[i * 4 + 2] = (uint8_t)(ctx.state[i] >> 8);
        out[i * 4 + 3] = (uint8_t)(ctx.state[i]);
    }
}

static void base64_encode(const uint8_t *in, size_t len, char *out) {
    static const char tbl[] = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
    size_t i = 0, j = 0;
    while (i < len) {
        uint32_t a = i < len ? in[i++] : 0;
        uint32_t b = i < len ? in[i++] : 0;
        uint32_t c = i < len ? in[i++] : 0;
        uint32_t triple = (a << 16) | (b << 8) | c;
        size_t rem = len - (i - 3);
        out[j++] = tbl[(triple >> 18) & 0x3F];
        out[j++] = tbl[(triple >> 12) & 0x3F];
        out[j++] = (rem > 1 || (i - 1 <= len && len % 3 != 1)) ? tbl[(triple >> 6) & 0x3F] : '=';
        out[j++] = (len % 3 == 0 || i <= len) ? tbl[triple & 0x3F] : '=';
    }
    /* Fix padding explicitly for exact byte length mod 3 */
    if (len % 3 == 1 && j >= 2) {
        out[j - 1] = '=';
        out[j - 2] = '=';
    } else if (len % 3 == 2 && j >= 1) {
        out[j - 1] = '=';
    }
    out[j] = '\0';
}

/* ---------- Small System / JSON Helpers ---------- */

static int read_first_line(const char *path, char *buf, size_t sz) {
    FILE *f = fopen(path, "r");
    if (!f) {
        if (sz > 0) buf[0] = '\0';
        return -1;
    }
    if (!fgets(buf, (int)sz, f)) {
        buf[0] = '\0';
        fclose(f);
        return -1;
    }
    fclose(f);
    size_t n = strlen(buf);
    while (n > 0 && (buf[n - 1] == '\n' || buf[n - 1] == '\r')) {
        buf[--n] = '\0';
    }
    return 0;
}

static void json_escape(const char *src, char *dst, size_t dst_sz) {
    size_t j = 0;
    for (size_t i = 0; src[i] != '\0' && j + 6 < dst_sz; i++) {
        unsigned char c = (unsigned char)src[i];
        if (c == '"' || c == '\\') {
            dst[j++] = '\\';
            dst[j++] = (char)c;
        } else if (c == '\n') {
            dst[j++] = '\\';
            dst[j++] = 'n';
        } else if (c == '\r') {
            dst[j++] = '\\';
            dst[j++] = 'r';
        } else if (c == '\t') {
            dst[j++] = '\\';
            dst[j++] = 't';
        } else if (c < 0x20) {
            j += (size_t)snprintf(dst + j, dst_sz - j, "\\u%04x", c);
        } else {
            dst[j++] = (char)c;
        }
    }
    dst[j] = '\0';
}

static bool get_iface_ipv4(const char *ifname, char *ip_out, size_t sz) {
    int fd = socket(AF_INET, SOCK_DGRAM, 0);
    if (fd < 0) return false;
    struct ifreq ifr;
    memset(&ifr, 0, sizeof(ifr));
    snprintf(ifr.ifr_name, IFNAMSIZ, "%s", ifname);
    bool ok = false;
    if (ioctl(fd, SIOCGIFADDR, &ifr) == 0) {
        struct sockaddr_in *sin = (struct sockaddr_in *)&ifr.ifr_addr;
        if (inet_ntop(AF_INET, &sin->sin_addr, ip_out, (socklen_t)sz)) {
            ok = true;
        }
    }
    close(fd);
    return ok;
}

static void find_lan_iface_ip(char *iface_out, size_t if_sz, char *ip_out, size_t ip_sz) {
    iface_out[0] = '\0';
    ip_out[0] = '\0';
    DIR *d = opendir("/sys/class/net");
    if (!d) return;
    struct dirent *ent;
    while ((ent = readdir(d)) != NULL) {
        const char *n = ent->d_name;
        if (strncmp(n, "eth", 3) == 0 || strncmp(n, "en", 2) == 0 || strncmp(n, "usb", 3) == 0) {
            char tmp_ip[64] = "";
            if (get_iface_ipv4(n, tmp_ip, sizeof(tmp_ip))) {
                snprintf(iface_out, if_sz, "%.31s", n);
                snprintf(ip_out, ip_sz, "%.63s", tmp_ip);
                break;
            }
        }
    }
    closedir(d);
}

static const char *detect_guest_root(void) {
    struct stat st;
    if (stat("/run/s8/switched_root", &st) == 0 || stat("/etc/os-release", &st) == 0) {
        return "/";
    }
    static const char *candidates[] = {"/mnt/rootfs", "/mnt/ubuntu", "/mnt/os"};
    for (size_t i = 0; i < sizeof(candidates) / sizeof(candidates[0]); i++) {
        char probe[256];
        snprintf(probe, sizeof(probe), "%s/bin", candidates[i]);
        if (stat(probe, &st) == 0 && S_ISDIR(st.st_mode)) {
            return candidates[i];
        }
        snprintf(probe, sizeof(probe), "%s/usr/bin", candidates[i]);
        if (stat(probe, &st) == 0 && S_ISDIR(st.st_mode)) {
            return candidates[i];
        }
    }
    return "";
}

static void detect_guest_os_name(const char *root, char *out, size_t sz) {
    snprintf(out, sz, "None");
    if (!root || !root[0]) return;
    char path[256];
    if (strcmp(root, "/") == 0) {
        snprintf(path, sizeof(path), "/etc/os-release");
    } else {
        snprintf(path, sizeof(path), "%s/etc/os-release", root);
    }
    FILE *f = fopen(path, "r");
    if (!f) {
        snprintf(out, sz, "Minimal Linux Rootfs");
        return;
    }
    char line[256];
    while (fgets(line, sizeof(line), f)) {
        if (strncmp(line, "PRETTY_NAME=", 12) == 0) {
            char *v = line + 12;
            size_t l = strlen(v);
            while (l > 0 && (v[l - 1] == '\n' || v[l - 1] == '\r' || v[l - 1] == '"')) v[--l] = '\0';
            if (*v == '"') v++;
            snprintf(out, sz, "%.127s", v);
            break;
        }
    }
    fclose(f);
}

/* Return PID (1 in native switch_root mode, or >1 for containerized guest) */
static pid_t find_guest_pid1(const char *guest_root) {
    if (!guest_root || !guest_root[0]) return 0;
    if (strcmp(guest_root, "/") == 0) {
        return 1;
    }
    DIR *d = opendir("/proc");
    if (!d) return 0;
    struct dirent *ent;
    pid_t found = 0;
    char expected[256];
    snprintf(expected, sizeof(expected), "%s", guest_root);

    while ((ent = readdir(d)) != NULL) {
        if (!isdigit((unsigned char)ent->d_name[0])) continue;
        pid_t pid = (pid_t)atoi(ent->d_name);
        if (pid <= 1) continue;
        char root_link[128], resolved[256], cmd_path[128], cmd[128];
        snprintf(root_link, sizeof(root_link), "/proc/%d/root", pid);
        ssize_t rl = readlink(root_link, resolved, sizeof(resolved) - 1);
        if (rl <= 0) continue;
        resolved[rl] = '\0';
        if (strcmp(resolved, expected) != 0) continue;

        snprintf(cmd_path, sizeof(cmd_path), "/proc/%d/comm", pid);
        if (read_first_line(cmd_path, cmd, sizeof(cmd)) == 0) {
            if (strcmp(cmd, "systemd") == 0 || strcmp(cmd, "init") == 0 || strcmp(cmd, "openrc-init") == 0) {
                found = pid;
                break;
            }
        }
    }
    closedir(d);
    return found;
}

static const char *pick_guest_shell(const char *root) {
    static const char *shells[] = {"/bin/bash", "/usr/bin/bash", "/bin/ash", "/bin/sh", "/usr/bin/sh"};
    char full[256];
    for (size_t i = 0; i < sizeof(shells) / sizeof(shells[0]); i++) {
        if (strcmp(root, "/") == 0) {
            if (access(shells[i], X_OK) == 0) return shells[i];
        } else {
            snprintf(full, sizeof(full), "%s%s", root, shells[i]);
            if (access(full, X_OK) == 0) return shells[i];
        }
    }
    return "/bin/sh";
}

/* ---------- Shell Launcher Inside Either AP or Guest OS ---------- */

static void exec_target_shell(const char *env_mode, const char *cmd_str, bool interactive) {
    const char *path_val = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/run/s8";
    const char *path_env = "PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/run/s8";
    setenv("PATH", path_val, 1);
    setenv("TERM", "xterm-256color", 1);
    setenv("HOME", "/root", 1);
    setenv("LANG", "C.UTF-8", 1);

    if (strcmp(env_mode, "os") == 0) {
        const char *root = detect_guest_root();
        if (root[0]) {
            const char *gsh = pick_guest_shell(root);
            if (strcmp(root, "/") == 0) {
                if (interactive) {
                    execl(gsh, gsh, "-l", (char *)NULL);
                    execl(gsh, gsh, (char *)NULL);
                } else {
                    execl(gsh, gsh, "-c", cmd_str, (char *)NULL);
                }
            }
            pid_t gpid = find_guest_pid1(root);
            if (gpid > 1 && access("/usr/bin/nsenter", X_OK) == 0) {
                char pid_s[24];
                snprintf(pid_s, sizeof(pid_s), "%d", (int)gpid);
                if (interactive) {
                    execl("/usr/bin/nsenter", "nsenter", "-t", pid_s, "-m", "-u", "-i", "-n", "-p",
                          "/usr/bin/env", path_env, "TERM=xterm-256color", "HOME=/root", gsh, "-l", (char *)NULL);
                } else {
                    execl("/usr/bin/nsenter", "nsenter", "-t", pid_s, "-m", "-u", "-i", "-n", "-p",
                          "/usr/bin/env", path_env, "HOME=/root", gsh, "-c", cmd_str, (char *)NULL);
                }
            }
            if (chroot(root) == 0 && chdir("/") == 0) {
                if (interactive) {
                    execl(gsh, gsh, "-l", (char *)NULL);
                    execl(gsh, gsh, (char *)NULL);
                } else {
                    execl(gsh, gsh, "-c", cmd_str, (char *)NULL);
                }
            }
        }
    }

    const char *ap_sh = (access("/run/s8/sh", X_OK) == 0) ? "/run/s8/sh" :
                        (access("/sbin/sh", X_OK) == 0) ? "/sbin/sh" : "/bin/sh";
    if (interactive) {
        execl(ap_sh, ap_sh, "-l", (char *)NULL);
        execl(ap_sh, ap_sh, (char *)NULL);
    } else {
        execl(ap_sh, ap_sh, "-c", cmd_str, (char *)NULL);
    }
    _exit(127);
}

/* ---------- HTTP / JSON Endpoints ---------- */

static void send_all(int fd, const void *buf, size_t len) {
    const uint8_t *p = (const uint8_t *)buf;
    size_t sent = 0;
    while (sent < len) {
        ssize_t n = write(fd, p + sent, len - sent);
        if (n <= 0) {
            if (n < 0 && errno == EINTR) continue;
            break;
        }
        sent += (size_t)n;
    }
}

static void send_http_json(int fd, int status, const char *json) {
    char hdr[512];
    size_t body_len = strlen(json);
    int hlen = snprintf(hdr, sizeof(hdr),
                        "HTTP/1.1 %d %s\r\n"
                        "Content-Type: application/json\r\n"
                        "Access-Control-Allow-Origin: *\r\n"
                        "Content-Length: %zu\r\n"
                        "Connection: close\r\n\r\n",
                        status, (status == 200) ? "OK" : "BAD REQUEST", body_len);
    if (hlen > 0) send_all(fd, hdr, (size_t)hlen);
    send_all(fd, json, body_len);
}

static void handle_info(int fd) {
    struct utsname u;
    uname(&u);

    char temp_s[32] = "0", batt_s[32] = "0", curr_s[32] = "0", dp_s[16] = "0";
    read_first_line("/sys/class/thermal/thermal_zone0/temp", temp_s, sizeof(temp_s));
    read_first_line("/sys/class/power_supply/battery/capacity", batt_s, sizeof(batt_s));
    read_first_line("/sys/class/power_supply/battery/current_now", curr_s, sizeof(curr_s));
    read_first_line("/sys/class/switch/hdmi/state", dp_s, sizeof(dp_s));

    char rndis_ip[64] = "", wlan_ip[64] = "", lan_if[32] = "", lan_ip[64] = "";
    get_iface_ipv4("rndis0", rndis_ip, sizeof(rndis_ip));
    get_iface_ipv4("wlan0", wlan_ip, sizeof(wlan_ip));
    find_lan_iface_ip(lan_if, sizeof(lan_if), lan_ip, sizeof(lan_ip));

    const char *root = detect_guest_root();
    char os_name[128], os_esc[256], pid1_comm[64] = "";
    detect_guest_os_name(root, os_name, sizeof(os_name));
    json_escape(os_name, os_esc, sizeof(os_esc));
    pid_t gpid = find_guest_pid1(root);
    read_first_line("/proc/1/comm", pid1_comm, sizeof(pid1_comm));
    const char *init_mode = (strcmp(pid1_comm, "systemd") == 0 || strcmp(root, "/") == 0) ? "native-systemd" : "initramfs";

    int t_raw = atoi(temp_s);
    double temp_c = (t_raw > 1000) ? (t_raw / 1000.0) : ((t_raw > 100) ? (t_raw / 10.0) : (double)t_raw);

    char out[2048];
    snprintf(out, sizeof(out),
             "{"
             "\"protocol\":\"rwp-v1\","
             "\"kernel\":\"%s\","
             "\"arch\":\"%s\","
             "\"init_mode\":\"%s\","
             "\"pid1_comm\":\"%s\","
             "\"temp_c\":%.1f,"
             "\"battery_pct\":%d,"
             "\"current_ma\":%d,"
             "\"dp_connected\":%s,"
             "\"rndis_ip\":\"%s\","
             "\"wlan_ip\":\"%s\","
             "\"lan_iface\":\"%s\","
             "\"lan_ip\":\"%s\","
             "\"guest_mounted\":%s,"
             "\"guest_root\":\"%s\","
             "\"guest_os\":\"%s\","
             "\"guest_pid1\":%d"
             "}",
             u.release, u.machine, init_mode, pid1_comm, temp_c, atoi(batt_s), atoi(curr_s),
             (atoi(dp_s) == 1) ? "true" : "false",
             rndis_ip, wlan_ip, lan_if, lan_ip,
             root[0] ? "true" : "false", root, os_esc, (int)gpid);
    send_http_json(fd, 200, out);
}

static bool extract_json_str(const char *json, const char *key, char *out, size_t sz) {
    char pat[64];
    snprintf(pat, sizeof(pat), "\"%s\"", key);
    const char *p = strstr(json, pat);
    if (!p) return false;
    p += strlen(pat);
    while (*p == ' ' || *p == '\t' || *p == ':') p++;
    if (*p != '"') return false;
    p++;
    size_t j = 0;
    while (*p && *p != '"' && j + 1 < sz) {
        if (*p == '\\' && p[1]) {
            p++;
            if (*p == 'n') out[j++] = '\n';
            else if (*p == 'r') out[j++] = '\r';
            else if (*p == 't') out[j++] = '\t';
            else out[j++] = *p;
        } else {
            out[j++] = *p;
        }
        p++;
    }
    out[j] = '\0';
    return true;
}

static void handle_exec(int fd, const char *body) {
    char env_mode[16] = "os";
    char cmd[4096] = "";
    extract_json_str(body, "env", env_mode, sizeof(env_mode));
    if (!extract_json_str(body, "cmd", cmd, sizeof(cmd)) || !cmd[0]) {
        send_http_json(fd, 400, "{\"error\":\"Missing cmd\"}");
        return;
    }

    int pfd[2];
    if (pipe(pfd) != 0) {
        send_http_json(fd, 500, "{\"error\":\"pipe failed\"}");
        return;
    }
    pid_t pid = fork();
    if (pid == 0) {
        close(pfd[0]);
        dup2(pfd[1], STDOUT_FILENO);
        dup2(pfd[1], STDERR_FILENO);
        close(pfd[1]);
        exec_target_shell(env_mode, cmd, false);
    }
    close(pfd[1]);

    char *raw = calloc(1, MAX_CMD_OUT + 1);
    size_t total = 0;
    if (raw) {
        while (total < MAX_CMD_OUT) {
            ssize_t n = read(pfd[0], raw + total, MAX_CMD_OUT - total);
            if (n <= 0) break;
            total += (size_t)n;
        }
        raw[total] = '\0';
    }
    close(pfd[0]);

    int status = 0;
    waitpid(pid, &status, 0);
    int exit_code = WIFEXITED(status) ? WEXITSTATUS(status) : 1;

    char *esc = malloc(MAX_CMD_OUT * 2 + 256);
    char *resp = malloc(MAX_CMD_OUT * 2 + 512);
    if (esc && resp) {
        json_escape(raw ? raw : "", esc, MAX_CMD_OUT * 2 + 200);
        snprintf(resp, MAX_CMD_OUT * 2 + 500,
                 "{\"exit_code\":%d,\"env\":\"%s\",\"output\":\"%s\"}",
                 exit_code, env_mode, esc);
        send_http_json(fd, 200, resp);
    } else {
        send_http_json(fd, 500, "{\"error\":\"oom\"}");
    }
    free(raw);
    free(esc);
    free(resp);
}

/* ---------- WebSocket PTY Session ---------- */

static void ws_send_frame(int fd, uint8_t opcode, const void *data, size_t len) {
    uint8_t hdr[10];
    size_t hlen = 0;
    hdr[0] = (uint8_t)(0x80 | (opcode & 0x0F));
    if (len < 126) {
        hdr[1] = (uint8_t)len;
        hlen = 2;
    } else if (len <= 65535) {
        hdr[1] = 126;
        hdr[2] = (uint8_t)(len >> 8);
        hdr[3] = (uint8_t)(len & 0xFF);
        hlen = 4;
    } else {
        hdr[1] = 127;
        for (int i = 0; i < 8; i++) hdr[2 + i] = (uint8_t)((uint64_t)len >> ((7 - i) * 8));
        hlen = 10;
    }
    send_all(fd, hdr, hlen);
    if (len > 0) send_all(fd, data, len);
}

static void handle_ws_pty(int client_fd, const char *req_hdr, const char *query) {
    const char *k = strcasestr(req_hdr, "Sec-WebSocket-Key:");
    if (!k) {
        send_http_json(client_fd, 400, "{\"error\":\"Missing Sec-WebSocket-Key\"}");
        return;
    }
    k += 18;
    while (*k == ' ' || *k == '\t') k++;
    char ws_key[128] = "";
    size_t ki = 0;
    while (k[ki] && k[ki] != '\r' && k[ki] != '\n' && ki + 1 < sizeof(ws_key)) {
        ws_key[ki] = k[ki];
        ki++;
    }
    ws_key[ki] = '\0';

    char combined[256];
    snprintf(combined, sizeof(combined), "%s%s", ws_key, WS_GUID);
    uint8_t sha[20];
    char accept_b64[64];
    sha1_digest((const uint8_t *)combined, strlen(combined), sha);
    base64_encode(sha, 20, accept_b64);

    char env_mode[16] = "os";
    int cols = 100, rows = 30;
    if (query) {
        if (strstr(query, "env=ap")) snprintf(env_mode, sizeof(env_mode), "ap");
        const char *cp = strstr(query, "cols=");
        if (cp) { int c = atoi(cp + 5); if (c > 10 && c < 500) cols = c; }
        const char *rp = strstr(query, "rows=");
        if (rp) { int r = atoi(rp + 5); if (r > 5 && r < 200) rows = r; }
    }

    int master_fd = -1;
    struct winsize ws = { .ws_row = (unsigned short)rows, .ws_col = (unsigned short)cols };
    pid_t child = forkpty(&master_fd, NULL, NULL, &ws);
    if (child < 0) {
        send_http_json(client_fd, 500, "{\"error\":\"forkpty failed\"}");
        return;
    }
    if (child == 0) {
        exec_target_shell(env_mode, "", true);
    }

    char upgrade_resp[512];
    int ulen = snprintf(upgrade_resp, sizeof(upgrade_resp),
                        "HTTP/1.1 101 Switching Protocols\r\n"
                        "Upgrade: websocket\r\n"
                        "Connection: Upgrade\r\n"
                        "Sec-WebSocket-Accept: %s\r\n\r\n",
                        accept_b64);
    send_all(client_fd, upgrade_resp, (size_t)ulen);

    fcntl(master_fd, F_SETFL, fcntl(master_fd, F_GETFL, 0) | O_NONBLOCK);
    uint8_t ws_buf[65536];
    size_t ws_len = 0;

    while (1) {
        struct pollfd fds[2] = {
            { .fd = client_fd, .events = POLLIN },
            { .fd = master_fd, .events = POLLIN }
        };
        int pr = poll(fds, 2, 1000);
        if (pr < 0) {
            if (errno == EINTR) continue;
            break;
        }
        if (fds[1].revents & POLLIN) {
            uint8_t pbuf[8192];
            ssize_t n = read(master_fd, pbuf, sizeof(pbuf));
            if (n > 0) {
                ws_send_frame(client_fd, 0x02, pbuf, (size_t)n);
            } else if (n == 0 || (n < 0 && errno != EAGAIN)) {
                break;
            }
        }
        if (fds[1].revents & (POLLHUP | POLLERR)) break;

        if (fds[0].revents & (POLLIN | POLLHUP | POLLERR)) {
            ssize_t n = read(client_fd, ws_buf + ws_len, sizeof(ws_buf) - ws_len);
            if (n <= 0) break;
            ws_len += (size_t)n;

            while (ws_len >= 2) {
                uint8_t op = ws_buf[0] & 0x0F;
                bool masked = (ws_buf[1] & 0x80) != 0;
                uint64_t plen = ws_buf[1] & 0x7F;
                size_t hdr_sz = 2;
                if (plen == 126) {
                    if (ws_len < 4) break;
                    plen = ((uint64_t)ws_buf[2] << 8) | ws_buf[3];
                    hdr_sz = 4;
                } else if (plen == 127) {
                    if (ws_len < 10) break;
                    plen = 0;
                    for (int i = 0; i < 8; i++) plen = (plen << 8) | ws_buf[2 + i];
                    hdr_sz = 10;
                }
                if (masked) hdr_sz += 4;
                if (plen > sizeof(ws_buf) - hdr_sz) {
                    ws_len = 0;
                    break;
                }
                if (ws_len < hdr_sz + plen) break;

                uint8_t *payload = ws_buf + hdr_sz;
                if (masked) {
                    uint8_t *m = ws_buf + hdr_sz - 4;
                    for (size_t i = 0; i < plen; i++) payload[i] ^= m[i & 3];
                }

                if (op == 0x08) {
                    ws_send_frame(client_fd, 0x08, NULL, 0);
                    goto done;
                } else if (op == 0x09) {
                    ws_send_frame(client_fd, 0x0A, payload, (size_t)plen);
                } else if (op == 0x01 || op == 0x02) {
                    if (op == 0x01 && plen > 16 && plen < 256 && memcmp(payload, "{\"type\":\"resize\"", 16) == 0) {
                        char tmp[256];
                        memcpy(tmp, payload, (size_t)plen);
                        tmp[plen] = '\0';
                        const char *cp = strstr(tmp, "\"cols\":");
                        const char *rp = strstr(tmp, "\"rows\":");
                        if (cp && rp) {
                            struct winsize nws = { .ws_row = (unsigned short)atoi(rp + 7), .ws_col = (unsigned short)atoi(cp + 7) };
                            if (nws.ws_row > 2 && nws.ws_col > 10) ioctl(master_fd, TIOCSWINSZ, &nws);
                        }
                    } else if (plen > 0) {
                        send_all(master_fd, payload, (size_t)plen);
                    }
                }

                size_t consumed = hdr_sz + (size_t)plen;
                if (consumed < ws_len) memmove(ws_buf, ws_buf + consumed, ws_len - consumed);
                ws_len -= consumed;
            }
        }
        int wst = 0;
        if (waitpid(child, &wst, WNOHANG) > 0) break;
    }

done:
    ws_send_frame(client_fd, 0x08, NULL, 0);
    close(master_fd);
    kill(child, SIGHUP);
    waitpid(child, NULL, 0);
}

static void handle_client(int client_fd) {
    char *req = calloc(1, MAX_REQ_BUF + 1);
    if (!req) {
        close(client_fd);
        return;
    }
    size_t total = 0;
    const char *hdr_end = NULL;
    while (total < MAX_REQ_BUF) {
        ssize_t n = read(client_fd, req + total, MAX_REQ_BUF - total);
        if (n <= 0) break;
        total += (size_t)n;
        req[total] = '\0';
        hdr_end = strstr(req, "\r\n\r\n");
        if (hdr_end) break;
    }
    if (!hdr_end) {
        free(req);
        close(client_fd);
        return;
    }

    size_t hdr_len = (size_t)(hdr_end - req) + 4;
    size_t content_len = 0;
    const char *cl = strcasestr(req, "Content-Length:");
    if (cl && cl < hdr_end) content_len = (size_t)strtoul(cl + 15, NULL, 10);
    if (content_len > MAX_REQ_BUF - hdr_len) content_len = MAX_REQ_BUF - hdr_len;
    while (total < hdr_len + content_len) {
        ssize_t n = read(client_fd, req + total, (hdr_len + content_len) - total);
        if (n <= 0) break;
        total += (size_t)n;
        req[total] = '\0';
    }

    char method[16] = "", path_raw[512] = "";
    sscanf(req, "%15s %511s", method, path_raw);
    char *q = strchr(path_raw, '?');
    const char *query = NULL;
    if (q) {
        *q = '\0';
        query = q + 1;
    }

    if (strcmp(path_raw, "/rwp/v1/health") == 0) {
        send_http_json(client_fd, 200, "{\"status\":\"ok\"}");
    } else if (strcmp(path_raw, "/rwp/v1/info") == 0) {
        handle_info(client_fd);
    } else if (strcmp(path_raw, "/rwp/v1/exec") == 0 && strcmp(method, "POST") == 0) {
        handle_exec(client_fd, req + hdr_len);
    } else if (strcmp(path_raw, "/rwp/v1/pty") == 0) {
        handle_ws_pty(client_fd, req, query);
    } else {
        send_http_json(client_fd, 404, "{\"error\":\"not found\"}");
    }

    free(req);
    close(client_fd);
}

int main(void) {
    signal(SIGCHLD, SIG_IGN);
    signal(SIGPIPE, SIG_IGN);

    int srv = socket(AF_INET, SOCK_STREAM, 0);
    if (srv < 0) return 1;
    int opt = 1;
    setsockopt(srv, SOL_SOCKET, SO_REUSEADDR, &opt, sizeof(opt));

    struct sockaddr_in addr;
    memset(&addr, 0, sizeof(addr));
    addr.sin_family = AF_INET;
    addr.sin_addr.s_addr = INADDR_ANY;
    addr.sin_port = htons(AGENT_PORT);

    if (bind(srv, (struct sockaddr *)&addr, sizeof(addr)) < 0) {
        perror("[s8_usb_agentd] bind");
        close(srv);
        return 1;
    }
    if (listen(srv, 16) < 0) {
        close(srv);
        return 1;
    }
    printf("[s8_usb_agentd] Listening on 0.0.0.0:%d (RWP-v1 + PTY WS)\n", AGENT_PORT);
    fflush(stdout);

    while (1) {
        int cfd = accept(srv, NULL, NULL);
        if (cfd < 0) {
            if (errno == EINTR) continue;
            break;
        }
        pid_t worker = fork();
        if (worker == 0) {
            close(srv);
            signal(SIGCHLD, SIG_DFL);
            handle_client(cfd);
            _exit(0);
        }
        close(cfd);
    }
    close(srv);
    return 0;
}
