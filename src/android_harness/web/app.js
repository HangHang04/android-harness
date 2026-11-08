const $ = (id) => document.getElementById(id);
let tasks = [],
  active = null,
  observation = null,
  selected = null,
  busy = false;
let taskRender = "",
  contextKey = "";
function notice(text) {
  $("notice").textContent = text;
}
async function api(path, data) {
  const response = await fetch("/api/" + path, {
    method: data === undefined ? "GET" : "POST",
    headers: { "Content-Type": "application/json" },
    body: data === undefined ? undefined : JSON.stringify(data),
  });
  const value = await response.json();
  if (!value.ok) throw Error(value.error.message);
  return value.result;
}
function page(name) {
  document.querySelectorAll(".page").forEach((s) => (s.hidden = s.id !== name));
  document.querySelectorAll("nav button").forEach((b) => {
    b.classList.toggle("selected", b.dataset.page === name);
    if (b.dataset.page === name) $("pageTitle").textContent = b.textContent;
  });
}
document
  .querySelectorAll("[data-page]")
  .forEach((b) => (b.onclick = () => page(b.dataset.page)));
function button(text, handler) {
  const b = document.createElement("button");
  b.textContent = text;
  b.onclick = () => safe(handler);
  return b;
}
async function safe(fn) {
  try {
    await fn();
  } catch (e) {
    notice(e.message);
  }
}
async function refresh() {
  try {
    const devices = await api("devices");
    $("devices").replaceChildren();
    $("deviceSelect").replaceChildren();
    for (const d of devices) {
      const row = document.createElement("div");
      row.className = "device";
      const tips = {
        device: "已连接 · 请保持解锁",
        unauthorized: "待授权 · 请在手机确认 RSA 弹窗",
        offline: "离线 · 请重新连接",
      };
      row.textContent =
        (d.model || d.serial) + " / " + (tips[d.state] || d.state);
      if (d.state === "device") {
        const o = new Option(d.model || d.serial, d.serial);
        $("deviceSelect").add(o);
        row.append(
          button("为此设备创建任务", () => {
            page("tasks");
            $("deviceSelect").value = d.serial;
          }),
        );
      }
      $("devices").append(row);
    }
    $("status").textContent = devices.length
      ? "发现 " + devices.length + " 台设备"
      : "等待连接";
    if (!devices.length)
      $("devices").textContent =
        "暂未发现设备。检查数据线或使用无线调试，再刷新。";
    notice("设备列表已更新。");
  } catch (e) {
    notice(e.message);
    $("devices").textContent =
      "请确认已安装 Android SDK Platform Tools，或设置 ANDROID_HARNESS_ADB。";
  }
}
async function poll() {
  tasks = await api("tasks");
  active = tasks.find((t) => t.state === "active");
  const nextKey = active ? active.id + "/" + active.events.length : "";
  if (nextKey !== contextKey || active?.busy) {
    contextKey = nextKey;
    selected = null;
    observation = null;
    $("tapNode").disabled = true;
    $("highlight").hidden = true;
    $("phone").hidden = true;
    $("screenEmpty").hidden = false;
    $("nodes").replaceChildren();
  }
  const render = JSON.stringify(tasks);
  if (render !== taskRender) {
    taskRender = render;
    $("taskList").replaceChildren();
    const states = {
      pending: "等待批准",
      active: "执行授权中",
      completed: "已完成",
      cancelled: "已停止",
      failed: "操作失败",
      expired: "授权已到期",
    };
    for (const t of [...tasks].reverse()) {
      const row = document.createElement("div");
      row.className = "task";
      const title = document.createElement("strong");
      title.textContent = t.goal + " · " + states[t.state];
      const detail = document.createElement("small");
      detail.textContent =
        t.serial +
        " / " +
        t.packages.join(", ") +
        " / " +
        t.capabilities.join(", ");
      row.append(title, detail);
      if (t.capabilities.includes("files")) {
        const roots = document.createElement("small");
        roots.textContent =
          "文件目录：" + t.local_root + " ↔ " + t.remote_root;
        row.append(roots);
      }
      if (t.state === "pending")
        row.append(
          button("批准本次任务", async () => {
            await api("approve", { task_id: t.id });
            notice("本次任务已批准。");
            await poll();
            page("work");
          }),
          button("拒绝", async () => {
            await api("stop", { task_id: t.id });
            await poll();
          }),
        );
      for (const event of t.events.slice(-5)) {
        const line = document.createElement("small");
        line.textContent =
          event.action +
          " / " +
          (event.ok ? "完成" : "失败") +
          " / " +
          event.duration +
          "s";
        row.append(line);
      }
      $("taskList").append(row);
    }
  }
  $("activeSummary").textContent = active
    ? active.goal +
      " · " +
      active.serial +
      " · " +
      active.packages.join(", ") +
      " · " +
      active.capabilities.join(", ") +
      " · 剩余 " +
      Math.max(0, Math.ceil((active.expires - Date.now() / 1000) / 60)) +
      " 分钟" +
      (active.busy ? " · 执行中" : "")
    : "当前没有活动任务";
  $("stop").disabled = !active && !tasks.some((t) => t.busy);
  $("complete").disabled = !active;
}
async function action(name, args = {}) {
  if (busy) return;
  if (!active) throw Error("请先创建并批准任务。");
  busy = true;
  selected = null;
  $("tapNode").disabled = true;
  try {
    notice("正在执行，请稍候…");
    const result = await api("action", {
      task_id: active.id,
      action: name,
      args,
    });
    notice("操作完成。");
    return result;
  } finally {
    busy = false;
    await poll();
  }
}
function showObservation(value) {
  observation = value;
  selected = null;
  $("highlight").hidden = true;
  $("tapNode").disabled = true;
  $("nodes").replaceChildren();
  $("captured").textContent =
    value.package + " · " + new Date(value.captured_at).toLocaleTimeString();
  if (value.image_base64) {
    $("phone").src = "data:image/png;base64," + value.image_base64;
    $("phone").hidden = false;
    $("screenEmpty").hidden = true;
  }
  for (const n of value.nodes.filter(
    (n) => n.text || n.content_desc || n.clickable,
  )) {
    const b = button(
      n.text || n.content_desc || n.resource_id || n.class_name,
      () => {
        selected = n;
        document
          .querySelectorAll(".node")
          .forEach((x) => x.classList.remove("selected"));
        b.classList.add("selected");
        $("tapNode").disabled = false;
        const [w, h] = value.device.size_px;
        const [l, t, r, bt] = n.bounds;
        Object.assign($("highlight").style, {
          left: (l / w) * 100 + "%",
          top: (t / h) * 100 + "%",
          width: ((r - l) / w) * 100 + "%",
          height: ((bt - t) / h) * 100 + "%",
        });
        $("highlight").hidden = false;
      },
    );
    b.className = "node";
    $("nodes").append(b);
  }
}
async function observe() {
  const r = await action("observe", { screenshot: true });
  if (r) showObservation(r);
}
async function mutate(name, args) {
  await action(name, args);
  if (active) await observe();
}
$("refresh").onclick = () => safe(refresh);
$("observe").onclick = () => safe(observe);
$("taskForm").onsubmit = (e) => {
  e.preventDefault();
  safe(async () => {
    const f = new FormData(e.target);
    await api("tasks", {
      goal: f.get("goal"),
      serial: f.get("serial"),
      packages: f
        .get("packages")
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean),
      capabilities: ["observe", "interact", "files"].filter((c) => f.has(c)),
      local_root: f.get("local_root"),
      remote_root: f.get("remote_root"),
    });
    notice("请核对右侧范围并批准任务。");
    await poll();
  });
};
$("wireless").onsubmit = (e) => {
  e.preventDefault();
  safe(async () => {
    const f = new FormData(e.target);
    try {
      await api("connect", {
        host: f.get("host"),
        port: Number(f.get("port")),
        pair: e.submitter.name === "pair",
        code: f.get("code"),
      });
      await refresh();
    } finally {
      e.target.elements.code.value = "";
    }
  });
};
$("stop").onclick = () =>
  safe(async () => {
    const t = active || tasks.find((t) => t.busy);
    if (t) await api("stop", { task_id: t.id });
    notice("已撤销授权；当前调用结束后停止，不再执行后续步骤。");
    await poll();
  });
$("complete").onclick = () =>
  safe(async () => {
    if (active) await api("complete", { task_id: active.id });
    await poll();
  });
document
  .querySelectorAll("[data-key]")
  .forEach(
    (b) =>
      (b.onclick = () => safe(() => mutate("key", { key: b.dataset.key }))),
  );
document
  .querySelectorAll("[data-swipe]")
  .forEach(
    (b) =>
      (b.onclick = () =>
        safe(() => mutate("swipe", { direction: b.dataset.swipe }))),
  );
$("type").onclick = () =>
  safe(async () => {
    const text = $("text").value;
    $("text").value = "";
    await mutate("type", { text });
  });
$("tapNode").onclick = () =>
  safe(async () => {
    if (!selected) return;
    const n = selected;
    await mutate("tap-element", {
      selector: {
        resource_id: n.resource_id,
        text: n.text,
        content_desc: n.content_desc,
        class_name: n.class_name,
      },
    });
  });
$("openApp").onclick = () =>
  safe(() => mutate("open-app", { package: $("package").value.trim() }));
$("openUrl").onclick = () =>
  safe(() =>
    mutate("open-url", {
      package: $("package").value.trim(),
      url: $("url").value.trim(),
    }),
  );
safe(async () => {
  const token = location.hash.slice(1);
  history.replaceState(null, "", "/");
  if (token) await api("bootstrap", { token });
  await refresh();
  await poll();
  $("config").textContent = JSON.stringify(await api("config"), null, 2);
  setInterval(() => safe(poll), 2000);
});
