import customtkinter as ctk
import threading


# ─────────────────────────── Add / Edit Server Modal ────────────────────────
class AddServerModal(ctk.CTkToplevel):
    def __init__(self, master, on_save_callback, sql_agent_module):
        super().__init__(master)
        self.title("Add SQL Server")
        self.geometry("420x560")
        self.resizable(False, False)
        self.attributes("-topmost", True)
        self.on_save_callback = on_save_callback
        self.sql_agent = sql_agent_module

        self.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(self, text="Server Configuration",
                     font=ctk.CTkFont(size=18, weight="bold")).grid(row=0, column=0, pady=(24, 4))
        ctk.CTkLabel(self, text="Connect to a SQL Server Agent instance",
                     font=ctk.CTkFont(size=12), text_color="gray").grid(row=1, column=0, pady=(0, 16))

        self.alias_entry = ctk.CTkEntry(self, placeholder_text="Server Alias (e.g. Production DB)", width=320)
        self.alias_entry.grid(row=2, column=0, pady=6)

        self.address_entry = ctk.CTkEntry(self, placeholder_text="Server Address / IP", width=320)
        self.address_entry.grid(row=3, column=0, pady=6)

        self.instance_entry = ctk.CTkEntry(self, placeholder_text="Instance (optional, e.g. SQLEXPRESS)", width=320)
        self.instance_entry.grid(row=4, column=0, pady=6)

        self.user_entry = ctk.CTkEntry(self, placeholder_text="Username (leave blank for Windows Auth)", width=320)
        self.user_entry.grid(row=5, column=0, pady=6)

        self.pass_entry = ctk.CTkEntry(self, placeholder_text="Password", show="*", width=320)
        self.pass_entry.grid(row=6, column=0, pady=6)

        # Button row
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.grid(row=7, column=0, pady=20)

        self.test_btn = ctk.CTkButton(btn_frame, text="Test Connection", width=140,
                                      fg_color="transparent", border_width=1,
                                      border_color="#6366f1", text_color="#6366f1",
                                      hover_color="#6366f1",
                                      command=self._test_connection)
        self.test_btn.pack(side="left", padx=6)

        self.save_btn = ctk.CTkButton(btn_frame, text="Save Server", width=140,
                                      fg_color="#4f46e5", hover_color="#4338ca",
                                      command=self._save_clicked)
        self.save_btn.pack(side="left", padx=6)

        self.msg_label = ctk.CTkLabel(self, text="", font=ctk.CTkFont(size=12))
        self.msg_label.grid(row=8, column=0)

    def _build_server_dict(self):
        return {
            "alias": self.alias_entry.get().strip(),
            "address": self.address_entry.get().strip(),
            "instance": self.instance_entry.get().strip(),
            "user": self.user_entry.get().strip(),
            "password": self.pass_entry.get().strip(),
        }

    def _test_connection(self):
        data = self._build_server_dict()
        if not data["alias"] or not data["address"]:
            self._set_msg("Alias and Address are required!", "#ef4444")
            return
        self.test_btn.configure(state="disabled", text="Testing...")
        self._set_msg("Connecting...", "gray")

        def run():
            ok, msg = self.sql_agent.test_connection(data)
            self.after(0, lambda: self._test_done(ok, msg))

        threading.Thread(target=run, daemon=True).start()

    def _test_done(self, ok, msg):
        self.test_btn.configure(state="normal", text="Test Connection")
        if ok:
            self._set_msg("✓  " + msg, "#10b981")
        else:
            self._set_msg("✗  " + msg[:80], "#ef4444")

    def _save_clicked(self):
        data = self._build_server_dict()
        if not data["alias"] or not data["address"]:
            self._set_msg("Alias and Address are required!", "#ef4444")
            return
        self.on_save_callback(data)
        self.destroy()

    def _set_msg(self, text, color="gray"):
        self.msg_label.configure(text=text, text_color=color)


# ─────────────────────────── Stats Bar ──────────────────────────────────────
class StatsBar(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color=('#e2e8f0', '#1e2030'), corner_radius=10)
        self.grid_columnconfigure((0, 1, 2, 3), weight=1)
        self._labels = {}
        specs = [
            ("total",     "Total Jobs",    ('#111827', 'white')),
            ("succeeded", "Succeeded",     "#10b981"),
            ("failed",    "Failed",        "#ef4444"),
            ("disabled",  "Disabled",      "#9ca3af"),
        ]
        for col, (key, title, color) in enumerate(specs):
            card = ctk.CTkFrame(self, fg_color="transparent")
            card.grid(row=0, column=col, padx=20, pady=12, sticky="w")
            val_lbl = ctk.CTkLabel(card, text="—", font=ctk.CTkFont(size=26, weight="bold"), text_color=color)
            val_lbl.pack(anchor="w")
            ctk.CTkLabel(card, text=title, font=ctk.CTkFont(size=11), text_color="gray").pack(anchor="w")
            self._labels[key] = val_lbl

    def update(self, jobs):
        total = len(jobs)
        succeeded = sum(1 for j in jobs if j["last_run_status"] == "Succeeded")
        failed = sum(1 for j in jobs if j["last_run_status"] == "Failed")
        disabled = sum(1 for j in jobs if not j["enabled"])
        self._labels["total"].configure(text=str(total))
        self._labels["succeeded"].configure(text=str(succeeded))
        self._labels["failed"].configure(text=str(failed))
        self._labels["disabled"].configure(text=str(disabled))

    def reset(self):
        for lbl in self._labels.values():
            lbl.configure(text="—")


# ─────────────────────────── Job History Modal ──────────────────────────────
class JobHistoryModal(ctk.CTkToplevel):
    def __init__(self, master, job_name, server, sql_agent_module):
        super().__init__(master)
        self.title(f"History — {job_name}")
        self.geometry("700x480")
        self.attributes("-topmost", True)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(self, text=f"Run History: {job_name}",
                     font=ctk.CTkFont(size=16, weight="bold")).grid(row=0, column=0, pady=(20, 10))

        self.scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll.grid(row=1, column=0, sticky="nsew", padx=20, pady=(0, 20))
        self.scroll.grid_columnconfigure((0, 1, 2), weight=1)
        self.scroll.grid_columnconfigure(3, weight=4)

        self._loading_lbl = ctk.CTkLabel(self.scroll, text="Loading history...", text_color="gray")
        self._loading_lbl.pack(pady=20)

        def fetch():
            ok, data = sql_agent_module.fetch_job_history(server, job_name)
            self.after(0, lambda: self._render(ok, data))

        threading.Thread(target=fetch, daemon=True).start()

    def _render(self, ok, data):
        self._loading_lbl.destroy()
        if not ok:
            ctk.CTkLabel(self.scroll, text=f"Error: {data}", text_color="#ef4444").pack(pady=10)
            return
        if not data:
            ctk.CTkLabel(self.scroll, text="No history found.", text_color="gray").pack(pady=20)
            return

        header_font = ctk.CTkFont(size=11, weight="bold")
        for col, text in enumerate(["Date / Time", "Status", "Duration", "Message"]):
            ctk.CTkLabel(self.scroll, text=text, font=header_font,
                         text_color="gray").grid(row=0, column=col, sticky="w", padx=8, pady=(0, 6))

        for row_idx, entry in enumerate(data, start=1):
            status = entry["status"]
            color = {"Succeeded": "#10b981", "Failed": "#ef4444",
                     "In Progress": "#f59e0b"}.get(status, "gray")

            dt_str = entry["run_datetime"].strftime("%Y-%m-%d %H:%M") if entry["run_datetime"] else "—"
            dur = entry["duration_seconds"]
            if dur is None:
                dur_str = "—"
            elif dur < 60:
                dur_str = f"{dur}s"
            else:
                dur_str = f"{dur//60}m {dur%60}s"

            msg = (entry["message"] or "").strip()

            ctk.CTkLabel(self.scroll, text=dt_str, font=ctk.CTkFont(size=12)).grid(row=row_idx, column=0, sticky="nw", padx=8, pady=6)
            ctk.CTkLabel(self.scroll, text=status, font=ctk.CTkFont(size=12, weight="bold"), text_color=color).grid(row=row_idx, column=1, sticky="nw", padx=8, pady=6)
            ctk.CTkLabel(self.scroll, text=dur_str, font=ctk.CTkFont(size=12)).grid(row=row_idx, column=2, sticky="nw", padx=8, pady=6)
            ctk.CTkLabel(self.scroll, text=msg, font=ctk.CTkFont(size=11), text_color="gray", justify="left", wraplength=400).grid(row=row_idx, column=3, sticky="nw", padx=8, pady=6)

            sep = ctk.CTkFrame(self.scroll, height=1, fg_color=('#cbd5e1', '#2a2a3d'))
            sep.grid(row=row_idx + 1000, column=0, columnspan=4, sticky="ew", pady=0)


# ─────────────────────────── Job Row ────────────────────────────────────────
class JobRow(ctk.CTkFrame):
    def __init__(self, master, job_data, run_callback, toggle_callback, history_callback, is_admin=True):
        super().__init__(master, fg_color="transparent", height=86)
        self.pack_propagate(False)
        self.grid_propagate(False)

        name_font = ctk.CTkFont(size=14, weight="bold")
        desc_font = ctk.CTkFont(size=11)

        # ── Name + description ──────────────────────────────────
        info_frame = ctk.CTkFrame(self, fg_color="transparent")
        info_frame.place(relx=0.0, rely=0.5, anchor="w", relwidth=0.33, x=8)

        name_color = ('#111827', 'white') if job_data["enabled"] else "#6b7280"
        ctk.CTkLabel(info_frame, text=job_data["name"], font=name_font,
                     text_color=name_color, justify="left", wraplength=280).pack(anchor="w")

        desc = job_data.get("description") or "No description"
        if desc == "No description available.":
            desc = "No description"
        ctk.CTkLabel(info_frame, text=desc,
                     font=desc_font, text_color="gray", justify="left", wraplength=280).pack(anchor="w")

        # ── Status badge ────────────────────────────────────────
        status = job_data["last_run_status"]
        status_color = {
            "Succeeded": "#10b981",
            "Failed": "#ef4444",
            "In Progress": "#f59e0b",
            "Canceled": "#6b7280",
        }.get(status, "gray")

        badge_frame = ctk.CTkFrame(self, fg_color="transparent", border_width=1, border_color=status_color, corner_radius=6)
        badge_frame.place(relx=0.34, rely=0.5, anchor="w", x=8)
        ctk.CTkLabel(badge_frame, text=status, text_color=status_color,
                     font=ctk.CTkFont(size=11, weight="bold"),
                     padx=8, pady=2).pack()

        # ── Dates ───────────────────────────────────────────────
        last_run = job_data.get("start_execution_date")
        last_str = last_run.strftime("%Y-%m-%d %H:%M") if last_run else "Never"

        dur = job_data.get("duration_seconds")
        if dur is not None and last_run:
            dur_str = f"  ({dur}s)" if dur < 60 else f"  ({dur//60}m {dur%60}s)"
        else:
            dur_str = ""

        ctk.CTkLabel(self, text=last_str + dur_str, font=ctk.CTkFont(size=12)).place(relx=0.48, rely=0.5, anchor="w", x=8)

        next_run = job_data.get("next_scheduled_run_date")
        next_str = next_run.strftime("%Y-%m-%d %H:%M") if next_run else "Not scheduled"
        ctk.CTkLabel(self, text=next_str, text_color="#9ca3af",
                     font=ctk.CTkFont(size=12)).place(relx=0.62, rely=0.5, anchor="w", x=8)

        # ── Action buttons ──────────────────────────────────────
        actions = ctk.CTkFrame(self, fg_color="transparent")
        actions.place(relx=0.76, rely=0.5, anchor="w", x=8)

        self.run_btn = ctk.CTkButton(
            actions, text="▶  Run", width=80,
            fg_color="transparent", border_width=1,
            border_color="#6366f1", text_color="#a5b4fc",
            hover_color="#312e81",
            state="normal" if job_data["enabled"] else "disabled",
            command=lambda: self._handle_run(job_data, run_callback)
        )
        self.run_btn.pack(side="left", padx=2)

        self.hist_btn = ctk.CTkButton(
            actions, text="📋", width=36,
            fg_color="transparent", border_width=1,
            border_color="#374151", text_color="#9ca3af",
            hover_color="#1f2937",
            command=lambda: history_callback(job_data["name"])
        )
        self.hist_btn.pack(side="left", padx=2)

        # ── Enable / Disable toggle ─────────────────────────────
        toggle_frame = ctk.CTkFrame(self, fg_color="transparent")
        toggle_frame.place(relx=0.92, rely=0.5, anchor="w", x=8)
        self.toggle_var = ctk.BooleanVar(value=bool(job_data["enabled"]))
        self.toggle_sw = ctk.CTkSwitch(
            toggle_frame, text="", variable=self.toggle_var,
            width=40, height=20,
            state="normal" if is_admin else "disabled",
            command=lambda: toggle_callback(job_data["name"], self.toggle_var.get(), self.toggle_sw)
        )
        self.toggle_sw.pack()
        ctk.CTkLabel(toggle_frame, text="Enabled" if job_data["enabled"] else "Disabled",
                     font=ctk.CTkFont(size=10), text_color="gray").pack()

        # ── Separator ───────────────────────────────────────────
        sep = ctk.CTkFrame(self, height=1, fg_color=('#cbd5e1', '#222338'))
        sep.place(relx=0, rely=1.0, relwidth=1.0, anchor="sw")

    def _handle_run(self, job_data, run_callback):
        self.run_btn.configure(state="disabled", text="Running...")
        run_callback(job_data["name"], self.run_btn)
