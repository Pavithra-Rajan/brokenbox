// ---- theme toggle ----
var root = document.documentElement;
var label = document.getElementById("theme-label");
function syncLabel() { label.textContent = root.getAttribute("data-theme") === "light" ? "LIGHT" : "DARK"; }
syncLabel();
document.getElementById("theme").addEventListener("click", function () {
  var next = root.getAttribute("data-theme") === "light" ? "dark" : "light";
  root.setAttribute("data-theme", next);
  try { localStorage.setItem("bb-theme", next); } catch (e) {}
  syncLabel();
});

// ---- desktop computer animation ----
(function () {
  var pc = document.getElementById("pc");
  var term = document.getElementById("term");
  var status = document.getElementById("pc-status");
  var reduced = window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches;
  var MAX = 15;
  var P = '<span class="tp">admin@brokenbox</span>:<span class="tb">~</span>$ ';
  var HP = '<span class="th">you@host</span>:<span class="tb">~</span>$ ';
  var lines = [];

  function sleep(ms) { return reduced ? Promise.resolve() : new Promise(function (r) { setTimeout(r, ms); }); }
  function draw(cursor) {
    var view = lines.slice(-MAX);
    if (cursor && view.length) view[view.length - 1] += '<span class="cur">█</span>';
    term.innerHTML = view.join("\n");
  }
  function health(state, text) { pc.setAttribute("data-state", state); status.textContent = text; }
  async function type(prompt, text) {
    lines.push(prompt); draw(true);
    await sleep(450);
    for (var i = 0; i < text.length; i++) {
      lines[lines.length - 1] += text[i]; draw(true);
      await sleep(55 + Math.random() * 70);
    }
    await sleep(300);
  }
  function pad(s, n, left) { s = String(s); while (s.length < n) s = left ? " " + s : s + " "; return s; }
  function topFrame(tick, hot) {
    var j = function (base, spread) { return (base + (Math.random() - 0.5) * spread).toFixed(1); };
    var procs = [
      [4242, "root", j(98.4, 1.2), "0.4", "48:1" + tick + ".07", "logspam"],
      [612, "root", j(0.8, 0.6), "1.1", "0:41.33", "systemd-journal"],
      [833, "www-data", j(0.3, 0.4), "2.4", "0:09.81", "nginx"],
      [733, "admin", "0.2", "0.3", "0:00.42", "sshd"],
      [988, "admin", "0.1", "0.2", "0:00.0" + (7 + tick), "top"],
      [1, "root", "0.0", "0.6", "0:03.11", "systemd"]
    ];
    var out = [
      "top - 14:02:1" + tick + " up 3d,  load avg: " + j(7.8, 0.3) + ", 6.91, 5.40",
      "Tasks:  97 total,   2 running,  95 sleeping",
      "%Cpu(s): " + j(99.1, 0.6) + " us,  0.7 sy,  0.0 ni,  0.2 id",
      "MiB Mem :  1987.4 total,    412.8 free",
      "MiB Swap:     0.0 total,      0.0 free",
      "",
      '<span class="row inv">' + pad("  PID USER     %CPU %MEM     TIME+ COMMAND", 56) + "</span>"
    ];
    procs.forEach(function (p, i) {
      var row = pad(p[0], 5, true) + " " + pad(p[1], 8) + " " + pad(p[2], 4, true) + " " +
                pad(p[3], 4, true) + " " + pad(p[4], 9, true) + " " + p[5];
      out.push(i === 0 && hot ? '<span class="row hot">' + pad(row, 56) + "</span>" : row);
    });
    return out;
  }

  async function loop() {
    do {
      health("bad", "load 7.82 · DEGRADED");
      term.classList.remove("off");
      lines = [
        '<span class="dim">Linux brokenbox 6.1.0-amd64 x86_64</span>',
        '<span class="warn">! load average above 7.0 for the last 12m</span>',
        ""
      ];
      await sleep(600);
      await type(P, "top");

      // top takes over the screen (alternate buffer)
      var shell = lines.slice();
      for (var t = 0; t < 5; t++) {
        lines = topFrame(t, t >= 1); draw(false);
        await sleep(900);
      }
      lines = shell;                      // pressed q
      await type(P, "sudo kill -9 4242");
      health("warn", "load 5.10 · RECOVERING");
      await sleep(500);
      await type(P, "uptime");
      lines.push(" 14:02:19 up 3d,  load average: 0.41, 4.12, 4.98");
      draw(false); await sleep(900);

      await type(P, "exit");
      lines.push("logout", "Connection to brokenbox closed.");
      draw(false); await sleep(400);
      await type(HP, "brokenbox check noisy-neighbour");
      lines.push('<span class="dim">checking noisy-neighbour ...</span>');
      draw(false); await sleep(1000);
      lines.push('<span class="ok">✔ PASS</span>  logspam is dead, load is normal');
      lines.push('<span class="dim">solved in 03:12 · best 02:58</span>');
      lines.push(HP);
      health("ok", "load 0.04 · HEALTHY");
      draw(true);
      if (reduced) return;
      await sleep(3000);
      term.classList.add("off");          // CRT power-off, then loop
      await sleep(700);
    } while (true);
  }
  loop();
})();

// ---- tabs ----
var tabs = Array.prototype.slice.call(document.querySelectorAll('[role="tab"]'));
function select(tab, focus) {
  tabs.forEach(function (t) {
    var on = t === tab;
    t.setAttribute("aria-selected", on);
    t.tabIndex = on ? 0 : -1;
    document.getElementById(t.getAttribute("aria-controls")).hidden = !on;
  });
  if (focus) tab.focus();
  history.replaceState(null, "", "#" + tab.getAttribute("aria-controls"));
}
tabs.forEach(function (t, i) {
  t.addEventListener("click", function () { select(t); });
  t.addEventListener("keydown", function (e) {
    var d = e.key === "ArrowRight" ? 1 : e.key === "ArrowLeft" ? -1 : 0;
    if (d) select(tabs[(i + d + tabs.length) % tabs.length], true);
  });
});
var initial = tabs.find(function (t) { return "#" + t.getAttribute("aria-controls") === location.hash; });
if (initial) select(initial);

// ---- scenarios ----
var SCENARIOS = [
  ["dpkg-stuck", "apt says it can't get the dpkg lock", "easy", "packages", 15],
  ["exec-203", "A service fails with status=203/EXEC", "easy", "systemd", 10],
  ["hosts-hijack", "The app talks to the wrong server", "easy", "network", 10],
  ["key-rejected", "SSH key rejected: Permission denied (publickey)", "easy", "access", 10],
  ["noexec-mystery", "Permission denied, even as root", "easy", "disk", 10],
  ["rule-order", "Firewall ACCEPT rule that doesn't work", "easy", "network", 10],
  ["silent-cron", "A cron job that never produces its report", "easy", "cron", 15],
  ["sudo-path", "sudo: command not found", "easy", "access", 10],
  ["zombie-horde", "Hundreds of zombie processes, and counting", "easy", "processes", 15],
  ["ghost-space", "Disk full, but du finds nothing", "medium", "disk", 15],
  ["inode-famine", "No space left on device, with space left", "medium", "disk", 15],
  ["pg-perms", "PostgreSQL won't start after chmod -R 777", "medium", "database", 15],
  ["restart-storm", "Service stuck at start-limit-hit", "medium", "systemd", 15],
  ["socket-502", "nginx 502 in front of a healthy app", "medium", "web", 15],
  ["tls-chain", "TLS works in browsers, fails with curl", "medium", "web", 15]
];
var tbody = document.querySelector("#scen-table tbody");
function render(f) {
  tbody.innerHTML = "";
  SCENARIOS.filter(function (s) { return f === "all" || s[2] === f || s[3] === f; })
    .forEach(function (s) {
      var tr = document.createElement("tr");
      tr.innerHTML = "<td><code>" + s[0] + "</code></td><td>" + s[1] +
        "</td><td><span class='badge " + s[2] + "'>" + s[2] + "</span></td>" +
        "<td class='kind'>" + s[3] + "</td><td>" + s[4] + "m</td>";
      tbody.appendChild(tr);
    });
}
render("all");
document.querySelectorAll(".filters button").forEach(function (b) {
  b.addEventListener("click", function () {
    document.querySelectorAll(".filters button").forEach(function (x) { x.classList.toggle("on", x === b); });
    render(b.dataset.f);
  });
});
