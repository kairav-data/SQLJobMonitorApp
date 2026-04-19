import customtkinter as ctk
import database
import sql_agent
from ui_components import AddServerModal, JobRow, StatsBar, JobHistoryModal
import threading

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class ToastNotification(ctk.CTkFrame):
    """Temporary bottom-right toast notification."""
    def __init__(self, master, message, color="#10b981", duration_ms=3000):
        super().__init__(master, fg_color=('#e2e8f0', '#1a1c29'), border_color=color,
                         border_width=1, corner_radius=8)
        ctk.CTkLabel(self, text=message, text_color=color,
                     font=ctk.CTkFont(size=12)).pack(padx=14, pady=8)
        self.place(relx=1.0, rely=1.0, anchor="se", x=-20, y=-20)
        master.after(duration_ms, self.destroy)


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("SQL Job Monitor")
        self.geometry("1200x760")
        self.minsize(900, 560)

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        self.active_server = None
        self.servers = database.load_servers()
        self.current_jobs = []
        self.sort_by = "name"
        self.sort_dir = "asc"
        self._search_query = ""
        self.current_user_role = None

        self._build_login_screen()

    # ─────────────────────────── LOGIN ──────────────────────────────────────
    def _build_login_screen(self):
        self.login_frame = ctk.CTkFrame(self, fg_color=('#f8fafc', '#0d0f1a'), corner_radius=0)
        self.login_frame.place(relx=0, rely=0, relwidth=1, relheight=1)

        card = ctk.CTkFrame(self.login_frame, corner_radius=12, fg_color=('#f1f5f9', '#151728'))
        card.place(relx=0.5, rely=0.5, anchor="center")

        ctk.CTkLabel(card, text="⬡", font=ctk.CTkFont(size=46), text_color="#6366f1").pack(pady=(30, 0))
        ctk.CTkLabel(card, text="SQL Job Monitor", font=ctk.CTkFont(size=22, weight="bold")).pack(pady=(5, 30))

        self.user_var = ctk.StringVar()
        self.pass_var = ctk.StringVar()

        ctk.CTkEntry(card, textvariable=self.user_var, placeholder_text="Username", width=280).pack(padx=30, pady=10)
        ctk.CTkEntry(card, textvariable=self.pass_var, placeholder_text="Password", show="•", width=280).pack(padx=30, pady=10)

        self.login_err_lbl = ctk.CTkLabel(card, text="", text_color="#ef4444", font=ctk.CTkFont(size=12))
        self.login_err_lbl.pack()

        ctk.CTkButton(card, text="Sign In", width=280, fg_color="#4f46e5", hover_color="#4338ca", command=self._do_login).pack(padx=30, pady=(10, 40))

    def _do_login(self):
        u = self.user_var.get().strip()
        p = self.pass_var.get()
        ok, role = database.authenticate(u, p)
        if ok:
            self.current_user_role = role
            self.login_frame.destroy()
            self._build_sidebar()
            self._build_main_content()
            self.refresh_server_list()
        else:
            self.login_err_lbl.configure(text="Invalid credentials.")

    # ─────────────────────────── UI BUILD ───────────────────────────────────

    def _build_sidebar(self):
        self.sidebar = ctk.CTkFrame(self, width=260, corner_radius=0, fg_color=('#ffffff', '#12141f'))
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_rowconfigure(2, weight=1)
        self.sidebar.grid_columnconfigure(0, weight=1)

        # Logo area
        logo_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        logo_frame.grid(row=0, column=0, sticky="ew", padx=20, pady=(24, 4))

        ctk.CTkLabel(logo_frame, text="⬡  SQL Monitor",
                     font=ctk.CTkFont(size=17, weight="bold")).pack(side="left")

        # Servers section
        srv_header = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        srv_header.grid(row=1, column=0, sticky="ew", padx=20, pady=(16, 6))

        ctk.CTkLabel(srv_header, text="SERVERS",
                     font=ctk.CTkFont(size=10, weight="bold"),
                     text_color="#6b7280").pack(side="left")

        if self.current_user_role == "admin":
            add_btn = ctk.CTkButton(srv_header, text="+", width=28, height=28,
                                    fg_color=('#e2e8f0', '#1e2030'), hover_color="#4f46e5",
                                    command=self.open_add_server)
            add_btn.pack(side="right")

        self.server_list_frame = ctk.CTkScrollableFrame(
            self.sidebar, fg_color="transparent", corner_radius=0)
        self.server_list_frame.grid(row=2, column=0, sticky="nsew", padx=8, pady=4)

        # Bottom area
        bottom = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        bottom.grid(row=3, column=0, sticky="ew", padx=20, pady=16)

        self.logout_btn = ctk.CTkButton(
            bottom, text="Log Out", fg_color="transparent",
            border_width=1, border_color="#ef4444", text_color="#ef4444",
            hover_color="#7f1d1d", command=self._do_logout
        )
        self.logout_btn.pack(fill="x")

    def _build_main_content(self):
        self.main = ctk.CTkFrame(self, fg_color=('#f8fafc', '#0d0f1a'), corner_radius=0)
        self.main.grid(row=0, column=1, sticky="nsew")
        self.main.grid_rowconfigure(3, weight=1)
        self.main.grid_columnconfigure(0, weight=1)

        # ── Top header ──────────────────────────────────────────
        header = ctk.CTkFrame(self.main, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=30, pady=(28, 0))
        header.grid_columnconfigure(0, weight=1)

        self.server_title = ctk.CTkLabel(
            header, text="Select a server",
            font=ctk.CTkFont(size=26, weight="bold"))
        self.server_title.grid(row=0, column=0, sticky="w")

        # Search box
        self.search_var = ctk.StringVar()
        self.search_var.trace_add("write", self._on_search_change)
        self.search_entry = ctk.CTkEntry(
            header, textvariable=self.search_var,
            placeholder_text="🔍  Search jobs...",
            width=240, state="disabled")
        self.search_entry.grid(row=0, column=1, padx=10)

        self.refresh_btn = ctk.CTkButton(
            header, text="↻  Refresh", width=110,
            state="disabled", command=self.load_jobs,
            fg_color="#4f46e5", hover_color="#4338ca")
        self.refresh_btn.grid(row=0, column=2)

        # ── Stats bar ───────────────────────────────────────────
        self.stats_bar = StatsBar(self.main)
        self.stats_bar.grid(row=1, column=0, sticky="ew", padx=30, pady=(16, 0))

        # ── Table header ────────────────────────────────────────
        th = ctk.CTkFrame(self.main, fg_color=('#f1f5f9', '#151728'), corner_radius=8, height=44)
        th.grid(row=2, column=0, sticky="ew", padx=(20, 36), pady=(14, 0))
        th.pack_propagate(False)
        th.grid_propagate(False)

        th_font = ctk.CTkFont(size=11, weight="bold")
        sortable = [("JOB NAME", "name", 0.0), 
                    ("STATUS", "last_run_status", 0.34),
                    ("LAST RUN", "start_execution_date", 0.48),
                    ("NEXT RUN", "next_scheduled_run_date", 0.62)]
        for label, col, rx in sortable:
            btn = ctk.CTkButton(
                th, text=label, fg_color="transparent",
                text_color="#6b7280", font=th_font, anchor="w",
                hover_color=('#e2e8f0', '#1e2030'),
                command=lambda c=col: self._sort_column(c)
            )
            btn.place(relx=rx, rely=0.5, anchor="w", x=8, relwidth=0.14 if rx > 0 else 0.33)

        ctk.CTkLabel(th, text="ACTIONS", font=th_font, text_color="#6b7280",
                     anchor="w").place(relx=0.76, rely=0.5, anchor="w", x=8)
        ctk.CTkLabel(th, text="ENABLED", font=th_font, text_color="#6b7280",
                     anchor="w").place(relx=0.92, rely=0.5, anchor="w", x=8)

        # ── Table body ──────────────────────────────────────────
        self.jobs_frame = ctk.CTkScrollableFrame(self.main, fg_color="transparent")
        self.jobs_frame.grid(row=3, column=0, sticky="nsew", padx=20, pady=(4, 20))

        # ── Bottom status ───────────────────────────────────────
        self.status_label = ctk.CTkLabel(self.main, text="",
                                         font=ctk.CTkFont(size=12))
        self.status_label.grid(row=4, column=0, pady=(0, 10))

    # ─────────────────────────── SERVERS ────────────────────────────────────

    def refresh_server_list(self):
        for w in self.server_list_frame.winfo_children():
            w.destroy()

        for srv in self.servers:
            is_active = self.active_server and self.active_server["id"] == srv["id"]
            row = ctk.CTkFrame(self.server_list_frame, fg_color=('#e2e8f0', '#1e2030') if is_active else "transparent",
                               corner_radius=6)
            row.pack(fill="x", pady=2)

            btn = ctk.CTkButton(
                row, text=srv["alias"], anchor="w",
                fg_color="transparent", text_color=('#111827', 'white'),
                hover_color=('#e2e8f0', '#1e2030'),
                command=lambda s=srv: self.select_server(s))
            btn.pack(side="left", fill="x", expand=True)

            if self.current_user_role == "admin":
                del_btn = ctk.CTkButton(
                    row, text="✕", width=28,
                    fg_color="transparent", text_color="#4b5563",
                    hover_color="#ef4444",
                    command=lambda sid=srv["id"]: self.delete_server(sid))
                del_btn.pack(side="right", padx=4)

    def open_add_server(self):
        AddServerModal(self, self.on_server_added, sql_agent)

    def on_server_added(self, data):
        self.servers = database.add_server(data)
        self.refresh_server_list()
        self._toast(f"Server '{data['alias']}' added.")

    def delete_server(self, srv_id):
        self.servers = database.delete_server(srv_id)
        if self.active_server and self.active_server["id"] == srv_id:
            self.active_server = None
            self.server_title.configure(text="Select a server")
            self.refresh_btn.configure(state="disabled")
            self.search_entry.configure(state="disabled")
            self.stats_bar.reset()
            self._clear_jobs()
        self.refresh_server_list()

    def select_server(self, server):
        self.active_server = server
        self.server_title.configure(text=server["alias"])
        self.refresh_btn.configure(state="normal")
        self.search_entry.configure(state="normal")
        self.refresh_server_list()
        self.load_jobs()

    # ─────────────────────────── JOBS ───────────────────────────────────────

    def _clear_jobs(self):
        for w in self.jobs_frame.winfo_children():
            w.destroy()

    def load_jobs(self):
        if not self.active_server:
            return
        self._clear_jobs()
        self.status_label.configure(text="Loading jobs...", text_color="gray")
        thread = threading.Thread(
            target=self._fetch_thread, args=(self.active_server,), daemon=True)
        thread.start()

    def _fetch_thread(self, server):
        ok, res = sql_agent.fetch_jobs(server)
        self.after(0, lambda: self._fetch_callback(ok, res))

    def _fetch_callback(self, ok, res):
        if not ok:
            self.status_label.configure(text=f"Error: {res}", text_color="#ef4444")
            return
        self.status_label.configure(text="")
        self.current_jobs = res
        self.stats_bar.update(res)
        if not res:
            ctk.CTkLabel(self.jobs_frame, text="No jobs found.",
                         text_color="gray").pack(pady=30)
            return
        self._render_jobs()

    def _on_search_change(self, *_):
        self._search_query = self.search_var.get().lower()
        if self.current_jobs:
            self._render_jobs()

    def _sort_column(self, col):
        if self.sort_by == col:
            self.sort_dir = "desc" if self.sort_dir == "asc" else "asc"
        else:
            self.sort_by = col
            self.sort_dir = "asc"
        self._render_jobs()

    def _render_jobs(self):
        self._clear_jobs()
        q = self._search_query
        jobs = [j for j in self.current_jobs
                if not q or q in j["name"].lower() or q in (j.get("description") or "").lower()]

        jobs.sort(key=lambda j: str(j.get(self.sort_by) or ""),
                  reverse=(self.sort_dir == "desc"))

        if not jobs:
            ctk.CTkLabel(self.jobs_frame, text="No jobs match your search.",
                         text_color="gray").pack(pady=30)
            return

        for job in jobs:
            row = JobRow(
                self.jobs_frame, job,
                run_callback=self.trigger_run_job,
                toggle_callback=self.toggle_job_enabled,
                history_callback=self.open_history,
                is_admin=(self.current_user_role == "admin")
            )
            row.pack(fill="x", pady=1)

    # ─────────────────────────── RUN JOB ────────────────────────────────────

    def trigger_run_job(self, job_name, btn_ref):
        thread = threading.Thread(
            target=self._run_thread,
            args=(self.active_server, job_name, btn_ref),
            daemon=True)
        thread.start()

    def _run_thread(self, server, job_name, btn_ref):
        ok, msg = sql_agent.run_job(server, job_name)
        self.after(0, lambda: self._run_callback(ok, msg, btn_ref))

    def _run_callback(self, ok, msg, btn_ref):
        if ok:
            self._toast(msg, "#10b981")
            self.after(2500, self.load_jobs)
        else:
            self._toast(f"Failed: {msg}", "#ef4444")
            if btn_ref.winfo_exists():
                btn_ref.configure(state="normal", text="▶  Run")

    # ─────────────────────────── TOGGLE ENABLE ──────────────────────────────

    def toggle_job_enabled(self, job_name, enabled, switch_ref):
        switch_ref.configure(state="disabled")

        def run():
            ok, msg = sql_agent.set_job_enabled(self.active_server, job_name, enabled)
            self.after(0, lambda: self._toggle_callback(ok, msg, switch_ref, job_name, enabled))

        threading.Thread(target=run, daemon=True).start()

    def _toggle_callback(self, ok, msg, switch_ref, job_name, enabled):
        if switch_ref.winfo_exists():
            switch_ref.configure(state="normal")
        if ok:
            self._toast(msg, "#10b981")
            self.after(500, self.load_jobs)
        else:
            self._toast(f"Failed: {msg}", "#ef4444")

    # ─────────────────────────── HISTORY ────────────────────────────────────

    def open_history(self, job_name):
        JobHistoryModal(self, job_name, self.active_server, sql_agent)

    # ─────────────────────────── HELPERS ────────────────────────────────────

    def _toast(self, message, color="#10b981"):
        ToastNotification(self, message, color=color)

    def _do_logout(self):
        self.current_user_role = None
        self.active_server = None
        self.current_jobs = []
        self._search_query = ""
        self.sidebar.destroy()
        self.main.destroy()
        self._build_login_screen()

if __name__ == "__main__":
    app = App()
    app.mainloop()
