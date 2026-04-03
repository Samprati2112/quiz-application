import customtkinter as ctk
from tkinter import messagebox, IntVar
import time

from database import (
    init_db, register_user, login_user,
    get_categories, get_questions, save_session,
    get_leaderboard, get_user_history, add_question,
    get_quiz_for_student, get_quiz_questions,
)
from docx_parser import TEACHER_CODE

ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")

P = {
    "bg":      "#f8fafc",
    "surface": "#eef2ff",
    "card":    "#ffffff",
    "border":  "#cbd5e1",
    "accent":  "#2563eb",
    "accent2": "#1d4ed8",
    "cyan":    "#0284c7",
    "green":   "#22c55e",
    "red":     "#ef4444",
    "yellow":  "#f59e0b",
    "text":    "#0f172a",
    "muted":   "#475569",
}

def _label(parent, text="", size=13, weight="normal", color=None, **kw):
    return ctk.CTkLabel(
        parent, text=text,
        font=ctk.CTkFont(size=size, weight=weight),
        text_color=color or P["text"], **kw,
    )


def _btn(parent, text, cmd, width=None, height=40, fg=None, hover=None,
         border=False, border_color=None, text_color=None, **kw):
    return ctk.CTkButton(
        parent, text=text, command=cmd,
        width=width or 0, height=height,
        corner_radius=10,
        fg_color=fg or P["accent"],
        hover_color=hover or P["accent2"],
        border_width=1 if border else 0,
        border_color=border_color or P["muted"],
        text_color=text_color or P["text"],
        font=ctk.CTkFont(size=14, weight="bold"),
        **kw,
    )


def _entry(parent, placeholder="", show=None, **kw):
    return ctk.CTkEntry(
        parent, placeholder_text=placeholder,
        height=42, corner_radius=8, show=show or "",
        fg_color=P["surface"],
        border_color=P["border"], border_width=1,
        text_color=P["text"],
        placeholder_text_color=P["muted"],
        **kw,
    )


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        init_db()
        self.title("QuizMaster Pro")
        self.geometry("880x640")
        self.resizable(False, False)
        self.configure(fg_color=P["bg"])
        self.current_user = None

        self.update_idletasks()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"880x640+{(sw - 880)//2}+{(sh - 640)//2}")

        container = ctk.CTkFrame(self, fg_color="transparent")
        container.pack(fill="both", expand=True)
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)

        self.frames = {}
        for Cls in (LoginFrame, MenuFrame, QuizFrame,
                ResultFrame, LeaderboardFrame, HistoryFrame):
            f = Cls(container, self)
            self.frames[Cls.__name__] = f
            f.grid(row=0, column=0, sticky="nsew")

        self.show("LoginFrame")

    def show(self, name, **kw):
        f = self.frames[name]
        if hasattr(f, "on_show"):
            f.on_show(**kw)
        f.tkraise()

    def logout(self):
        self.current_user = None
        self.deiconify()
        self.show("LoginFrame")


class LoginFrame(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color=P["bg"])
        self.app = app
        self._teacher_win = None
        self._build()

    def _build(self):
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(pady=(60, 28))
        _label(top, "🧠", size=46).pack()
        _label(top, "QuizMaster Pro", size=30, weight="bold",
               color=P["accent"]).pack(pady=(4, 0))
        _label(top, "Challenge yourself. Track your progress.",
               size=13, color=P["muted"]).pack(pady=(4, 0))

        card = ctk.CTkFrame(self, fg_color=P["card"], corner_radius=18,
                            width=420, height=380)
        card.pack()
        card.pack_propagate(False)

        self.tab = ctk.CTkTabview(
            card, fg_color="transparent",
            segmented_button_fg_color=P["surface"],
            segmented_button_selected_color=P["accent"],
            segmented_button_selected_hover_color=P["accent2"],
            segmented_button_unselected_hover_color=P["border"],
        )
        self.tab.pack(fill="both", expand=True, padx=20, pady=10)
        self.tab.add("Login")
        self.tab.add("Register")

        lt = self.tab.tab("Login")
        _label(lt, "Username", size=12, color=P["muted"]).pack(anchor="w", pady=(8, 2))
        self.lu = _entry(lt, "Enter username")
        self.lu.pack(fill="x")
        _label(lt, "Password", size=12, color=P["muted"]).pack(anchor="w", pady=(8, 2))
        self.lp = _entry(lt, "Enter password", show="*")
        self.lp.pack(fill="x")
        self.lm = _label(lt, size=12, color=P["red"])
        self.lm.pack(pady=6)
        _btn(lt, "Login  →", self._login, height=42).pack(fill="x")
        self.lu.bind("<Return>", lambda e: self._login())
        self.lp.bind("<Return>", lambda e: self._login())

        rt = self.tab.tab("Register")
        _label(rt, "Username", size=12, color=P["muted"]).pack(anchor="w", pady=(6, 2))
        self.ru = _entry(rt, "Choose username (3+ chars)")
        self.ru.pack(fill="x")
        _label(rt, "Password", size=12, color=P["muted"]).pack(anchor="w", pady=(6, 2))
        self.rp = _entry(rt, "Choose password (4+ chars)", show="*")
        self.rp.pack(fill="x")
        _label(rt, "Teacher Code  (optional — leave blank for student)",
               size=11, color=P["muted"]).pack(anchor="w", pady=(6, 2))
        self.rc = _entry(rt, "Enter teacher code if you are a teacher")
        self.rc.pack(fill="x")
        self.rm = _label(rt, size=12)
        self.rm.pack(pady=6)
        _btn(rt, "Create Account", self._handle_register, height=40).pack(fill="x")

    def _login(self):
        ok, data = login_user(self.lu.get().strip(), self.lp.get())
        if not ok:
            self.lm.configure(text=f"✗  {data}", text_color=P["red"])
            return

        self.app.current_user = data
        self.lu.delete(0, "end")
        self.lp.delete(0, "end")
        self.lm.configure(text="")

        if data.get("role") == "teacher":
            self._open_teacher_dashboard(data)
        else:
            self.app.show("MenuFrame")

    def _open_teacher_dashboard(self, user):
        from teacher_dashboard import TeacherDashboard

        self.app.withdraw()

        td = TeacherDashboard(self.app, user)

        def _on_close():
            td.destroy()
            self.app.current_user = None
            self.app.deiconify()
            self.app.show("LoginFrame")

        td.protocol("WM_DELETE_WINDOW", _on_close)

    def _handle_register(self):
        u  = self.ru.get().strip()
        pw = self.rp.get()
        tc = self.rc.get().strip()

        if len(u) < 3:
            self.rm.configure(
                text="✗  Username must be 3+ characters", text_color=P["red"])
            return
        if len(pw) < 4:
            self.rm.configure(
                text="✗  Password must be 4+ characters", text_color=P["red"])
            return

        if tc and tc != TEACHER_CODE:
            self.rm.configure(
                text="✗  Invalid teacher code. Leave blank for student account.",
                text_color=P["red"],
            )
            return

        role = "teacher" if tc else "student"
        ok, msg = register_user(u, pw, role)
        if ok:
            suffix = "  (Teacher account)" if role == "teacher" else ""
            self.rm.configure(
                text=f"✓  Account created{suffix}! Please log in.",
                text_color=P["green"],
            )
            self.ru.delete(0, "end")
            self.rp.delete(0, "end")
            self.rc.delete(0, "end")
            self.tab.set("Login")
        else:
            self.rm.configure(text=f"✗  {msg}", text_color=P["red"])


class MenuFrame(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color=P["bg"])
        self.app = app
        self._build()

    def on_show(self):
        u = self.app.current_user
        self.welcome.configure(text=f"Welcome back, {u['username']} 👋")
        self.code_in.delete(0, "end")
        self.start_msg.configure(text="")

    def _build(self):
        nav = ctk.CTkFrame(self, fg_color=P["card"], corner_radius=0, height=62)
        nav.pack(fill="x")
        nav.pack_propagate(False)
        _label(nav, "🧠  QuizMaster Pro", size=18, weight="bold",
               color=P["accent"]).pack(side="left", padx=22)
        self.welcome = _label(nav, size=13, color=P["muted"])
        self.welcome.pack(side="left", padx=8)
        _btn(nav, "Logout", self.app.logout, width=90, height=32,
             fg="transparent", border=True, text_color=P["muted"],
             hover=P["surface"]).pack(side="right", padx=20)

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=30, pady=24)
        body.columnconfigure(0, weight=3)
        body.columnconfigure(1, weight=2)
        body.rowconfigure(0, weight=1)

        left = ctk.CTkFrame(body, fg_color=P["card"], corner_radius=16)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 12))

        _label(left, "Start Official Test", size=20, weight="bold").pack(
            anchor="w", padx=24, pady=(22, 4))
        _label(left, "Enter the teacher-provided test code to begin.",
               size=12, color=P["muted"]).pack(anchor="w", padx=24, pady=(0, 18))

        _label(left, "Test Code", size=12, color=P["muted"]).pack(anchor="w", padx=24)
        self.code_in = _entry(left, "Example: MIDSEM101")
        self.code_in.pack(fill="x", padx=24, pady=(4, 12))
        self.code_in.bind("<Return>", lambda e: self._start())

        self.start_msg = _label(left, size=12, color=P["muted"])
        self.start_msg.pack(anchor="w", padx=24, pady=(0, 8))

        _btn(left, "🚀   Start Test", self._start, height=48).pack(
            fill="x", padx=24, pady=(0, 24))

        right = ctk.CTkFrame(body, fg_color="transparent")
        right.grid(row=0, column=1, sticky="nsew")

        for icon, label, frame, color in [
            ("🏆", "Leaderboard",   "LeaderboardFrame", P["yellow"]),
            ("📊", "My History",    "HistoryFrame",      P["cyan"]),
        ]:
            card = ctk.CTkFrame(right, fg_color=P["card"], corner_radius=14, height=90)
            card.pack(fill="x", pady=8)
            card.pack_propagate(False)
            inner = ctk.CTkFrame(card, fg_color="transparent")
            inner.pack(expand=True)
            _label(inner, icon, size=28).pack()
            _label(inner, label, size=13, weight="bold", color=color).pack()
            card.bind("<Button-1>", lambda e, f=frame: self.app.show(f))
            card.bind("<Enter>",    lambda e, c=card: c.configure(fg_color=P["surface"]))
            card.bind("<Leave>",    lambda e, c=card: c.configure(fg_color=P["card"]))
            for child in card.winfo_children():
                child.bind("<Button-1>", lambda e, f=frame: self.app.show(f))

    def _start(self):
        code = self.code_in.get().strip().upper()
        if not code:
            self.start_msg.configure(
                text="✗  Enter a test code from your teacher.", text_color=P["red"])
            return

        try:
            quiz = get_quiz_for_student(code, self.app.current_user["id"])
        except ValueError as exc:
            self.start_msg.configure(text=f"✗  {exc}", text_color=P["red"])
            return
        if not quiz:
            self.start_msg.configure(
                text="✗  Invalid code. Please check and try again.",
                text_color=P["red"],
            )
            return

        questions = get_quiz_questions(quiz["id"])
        if not questions:
            messagebox.showwarning(
                "No Questions",
                "This test has no questions yet. Ask your teacher to upload questions.",
            )
            return
        self.start_msg.configure(
            text=f"✓  Starting: {quiz['name']} ({quiz['code']})",
            text_color=P["green"],
        )
        self.app.show("QuizFrame", questions=questions, quiz=quiz)


class QuizFrame(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color=P["bg"])
        self.app = app
        self.questions = []
        self.idx = self.score = 0
        self.timer_id = None
        self.time_left = 0
        self.total_time = 0
        self.warned_marks = set()
        self.start_ts = 0
        self.wrong = []
        self._build()

    def on_show(self, questions, quiz):
        self.questions = questions
        self.quiz = quiz
        self.category = quiz.get("name")
        self.difficulty = "Official Test"
        self.idx = self.score = 0
        self.wrong = []
        self.warned_marks = set()
        self.total_time = int(quiz.get("duration_minutes", 10)) * 60
        self.time_left = self.total_time
        self.start_ts = time.time()
        self.score_lbl.configure(text="Score: 0")
        self._load()
        self._tick_start()

    def _build(self):
        bar = ctk.CTkFrame(self, fg_color=P["card"], corner_radius=0, height=56)
        bar.pack(fill="x")
        bar.pack_propagate(False)
        self.q_lbl    = _label(bar, "Question 1/10", size=13, color=P["muted"])
        self.q_lbl.pack(side="left", padx=22)
        self.score_lbl = _label(bar, "Score: 0", size=14, weight="bold", color=P["green"])
        self.score_lbl.pack(side="right", padx=22)
        self.timer_lbl = _label(bar, "⏱  10:00", size=15,
                                weight="bold", color=P["yellow"])
        self.timer_lbl.pack(side="right", padx=14)

        self.prog = ctk.CTkProgressBar(
            self, progress_color=P["accent"],
            fg_color=P["border"], height=6, corner_radius=0,
        )
        self.prog.set(0)
        self.prog.pack(fill="x")

        qa = ctk.CTkFrame(self, fg_color="transparent")
        qa.pack(fill="x", padx=40, pady=(28, 10))
        self.meta_lbl = _label(qa, size=11, color=P["cyan"])
        self.meta_lbl.pack(anchor="w")
        self.ques_lbl = _label(qa, size=17, weight="bold",
                               wraplength=760, justify="left")
        self.ques_lbl.pack(anchor="w", pady=(6, 0))

        cf = ctk.CTkFrame(self, fg_color="transparent")
        cf.pack(fill="both", expand=True, padx=40, pady=6)
        cf.columnconfigure((0, 1), weight=1)
        cf.rowconfigure((0, 1), weight=1)

        self.btns = []
        for i in range(4):
            b = ctk.CTkButton(
                cf, text="", height=72, corner_radius=12,
                fg_color=P["card"], hover_color=P["surface"],
                border_width=2, border_color=P["border"],
                text_color=P["text"], font=ctk.CTkFont(size=13),
                anchor="w", command=lambda x=i: self._answer(x),
            )
            b.grid(row=i // 2, column=i % 2, padx=8, pady=7, sticky="nsew")
            self.btns.append(b)

        bot = ctk.CTkFrame(self, fg_color="transparent", height=64)
        bot.pack(fill="x", padx=40, pady=(0, 16))
        bot.pack_propagate(False)
        self.fb_lbl = _label(bot, size=15, weight="bold")
        self.fb_lbl.pack(side="left", pady=16)
        self.next_btn = _btn(bot, "Next  →", self._next, width=130, height=40)
        self.next_btn.configure(state="disabled")
        self.next_btn.pack(side="right", pady=12)

    def _load(self):
        q = self.questions[self.idx]
        n = len(self.questions)
        self.q_lbl.configure(text=f"Question  {self.idx + 1} / {n}")
        self.prog.set(self.idx / n)
        self.meta_lbl.configure(
            text=f"{q.get('category', '')}   •   {q.get('difficulty', '')}")
        self.ques_lbl.configure(text=q["question"])
        self.fb_lbl.configure(text="")
        self.next_btn.configure(state="disabled")
        for i, b in enumerate(self.btns):
            ch = q["choices"][i] if i < len(q["choices"]) else ""
            b.configure(text=f"   {ch}", state="normal",
                        fg_color=P["card"], border_color=P["border"],
                        text_color=P["text"])

    def _tick_start(self):
        if self.timer_id:
            self.after_cancel(self.timer_id)
        self._tick()

    def _tick(self):
        if self.time_left <= 0:
            self._timeout(); return

        if self.time_left in (300, 60) and self.time_left not in self.warned_marks:
            self.warned_marks.add(self.time_left)
            mins_left = self.time_left // 60
            messagebox.showwarning(
                "Time Warning",
                f"Only {mins_left} minute(s) remaining for this test.",
                parent=self,
            )

        mins = self.time_left // 60
        secs = self.time_left % 60
        color = (P["green"] if self.time_left > 300
                 else P["yellow"] if self.time_left > 120 else P["red"])
        self.timer_lbl.configure(text=f"⏱  {mins:02d}:{secs:02d}", text_color=color)
        self.time_left -= 1
        self.timer_id = self.after(1000, self._tick)

    def _timeout(self):
        if self.timer_id:
            self.after_cancel(self.timer_id)
            self.timer_id = None

        for b in self.btns:
            b.configure(state="disabled")
        self.next_btn.configure(state="disabled")

        elapsed = int(time.time() - self.start_ts)
        save_session(self.app.current_user["id"],
                     self.score, len(self.questions),
                     self.category, self.difficulty, elapsed,
                     quiz_id=self.quiz["id"])

        self.app.show("ResultFrame",
                      score=self.score,
                      total=len(self.questions),
                      elapsed=elapsed,
                      wrong=self.wrong,
                      category=self.category,
                      difficulty=self.difficulty,
                      quiz=self.quiz)

    def _answer(self, idx):
        q       = self.questions[self.idx]
        correct = q["answer"]
        chosen  = self.btns[idx].cget("text").strip()

        for i, b in enumerate(self.btns):
            b.configure(state="disabled")
            ch = b.cget("text").strip()
            if ch == correct:
                b.configure(fg_color=P["green"], border_color=P["green"])
            elif i == idx:
                b.configure(fg_color=P["red"],   border_color=P["red"])

        if chosen == correct:
            self.score += 1
            self.score_lbl.configure(text=f"Score: {self.score}")
            self.fb_lbl.configure(text="✓  Correct!", text_color=P["green"])
        else:
            self.fb_lbl.configure(text="✗  Incorrect!", text_color=P["red"])
            self.wrong.append({"question": q["question"],
                               "your_answer": chosen, "correct": correct})
        self.next_btn.configure(state="normal")

    def _next(self):
        self.idx += 1
        if self.idx < len(self.questions):
            self._load()
        else:
            if self.timer_id:
                self.after_cancel(self.timer_id)
            self.prog.set(1.0)
            elapsed = int(time.time() - self.start_ts)
            save_session(self.app.current_user["id"],
                         self.score, len(self.questions),
                         self.category, self.difficulty, elapsed,
                         quiz_id=self.quiz["id"])

            self.app.show("ResultFrame",
                          score=self.score,
                          total=len(self.questions),
                          elapsed=elapsed,
                          wrong=self.wrong,
                          category=self.category,
                          difficulty=self.difficulty,
                          quiz=self.quiz)


class ResultFrame(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color=P["bg"])
        self.app = app
        self._build()

    def on_show(self, score, total, elapsed, wrong, category, difficulty, quiz=None):
        pct   = round(score / total * 100)
        grade = ("S" if pct == 100 else "A" if pct >= 90 else
                 "B" if pct >= 75 else "C" if pct >= 60 else
                 "D" if pct >= 50 else "F")
        col = P["green"] if pct >= 75 else P["yellow"] if pct >= 50 else P["red"]

        self.score_v.configure(text=f"{score}/{total}", text_color=col)
        self.pct_v.configure(text=f"{pct}%",             text_color=col)
        self.grade_v.configure(text=grade,               text_color=col)
        self.time_v.configure(text=f"{elapsed}s")
        if quiz:
            self.meta_v.configure(text=f"{quiz['name']}  •  Code: {quiz['code']}")
        else:
            self.meta_v.configure(text=f"{category}  •  {difficulty}")

        for w in self.review.winfo_children():
            w.destroy()
        if wrong:
            _label(self.review, f"Review  —  {len(wrong)} incorrect",
                   size=13, weight="bold", color=P["red"]).pack(
                anchor="w", padx=16, pady=(14, 6))
            for wa in wrong:
                card = ctk.CTkFrame(self.review, fg_color=P["surface"],
                                    corner_radius=10)
                card.pack(fill="x", padx=16, pady=4)
                _label(card, wa["question"], size=12, color=P["text"],
                       wraplength=620, justify="left").pack(
                    anchor="w", padx=14, pady=(10, 2))
                _label(card, f"Your answer:  {wa['your_answer']}",
                       size=11, color=P["red"]).pack(anchor="w", padx=14)
                _label(card, f"Correct:  {wa['correct']}",
                       size=11, color=P["green"]).pack(
                    anchor="w", padx=14, pady=(0, 10))
        else:
            _label(self.review, "🎉  Perfect score — no wrong answers!",
                   size=14, color=P["green"]).pack(pady=30)

    def _build(self):
        hdr = ctk.CTkFrame(self, fg_color=P["card"], corner_radius=0, height=160)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        _label(hdr, "Quiz Complete!", size=22, weight="bold").pack(pady=(18, 8))
        row = ctk.CTkFrame(hdr, fg_color="transparent")
        row.pack()
        for title, attr in [("Score","score_v"),("Percentage","pct_v"),
                             ("Grade","grade_v"),("Time","time_v")]:
            cell = ctk.CTkFrame(row, fg_color=P["surface"],
                                corner_radius=10, width=140, height=60)
            cell.pack(side="left", padx=6)
            cell.pack_propagate(False)
            lbl = _label(cell, size=22, weight="bold")
            lbl.pack(pady=(8, 0))
            _label(cell, title, size=10, color=P["muted"]).pack()
            setattr(self, attr, lbl)
        self.meta_v = _label(hdr, size=11, color=P["muted"])
        self.meta_v.pack(pady=(6, 0))

        self.review = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.review.pack(fill="both", expand=True)

        bot = ctk.CTkFrame(self, fg_color=P["card"], corner_radius=0, height=62)
        bot.pack(fill="x", side="bottom")
        bot.pack_propagate(False)
        _btn(bot, "🏠  Menu", lambda: self.app.show("MenuFrame"),
             width=130, height=36, fg="transparent", border=True,
             text_color=P["muted"], hover=P["surface"]).pack(
            side="left", padx=20, pady=12)
        _btn(bot, "🏆  Leaderboard", lambda: self.app.show("LeaderboardFrame"),
             width=160, height=36, fg="transparent", border=True,
             border_color=P["cyan"], text_color=P["cyan"],
             hover=P["surface"]).pack(side="left", padx=6, pady=12)
        _btn(bot, "🔄  Play Again", lambda: self.app.show("MenuFrame"),
             width=140, height=36).pack(side="right", padx=20, pady=12)


class LeaderboardFrame(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color=P["bg"])
        self.app = app
        self._build()

    def on_show(self):
        for w in self.body.winfo_children():
            w.destroy()
        rows  = get_leaderboard()
        cols  = ["Rank", "Player", "Best %", "Quizzes", "Total Correct"]
        widths = [60, 220, 110, 100, 130]
        hr = ctk.CTkFrame(self.body, fg_color=P["surface"], corner_radius=8)
        hr.pack(fill="x", pady=(0, 6))
        for h, w in zip(cols, widths):
            _label(hr, h, size=11, weight="bold", color=P["muted"],
                   width=w, anchor="center").pack(side="left", padx=4, pady=10)
        medals = ["🥇","🥈","🥉"]
        for i, r in enumerate(rows):
            rw = ctk.CTkFrame(self.body, fg_color=P["card"], corner_radius=8)
            rw.pack(fill="x", pady=3)
            rank = medals[i] if i < 3 else str(i + 1)
            rc   = P["yellow"] if i < 3 else P["text"]
            for val, w in zip(
                [rank, r["username"], f"{r['best_pct']}%",
                 str(r["quizzes"]), str(r["total_correct"])], widths
            ):
                _label(rw, val, size=13,
                       color=rc if val == rank else P["text"],
                       width=w, anchor="center").pack(side="left", padx=4, pady=12)

    def _build(self):
        nav = ctk.CTkFrame(self, fg_color=P["card"], corner_radius=0, height=62)
        nav.pack(fill="x")
        nav.pack_propagate(False)
        _label(nav, "🏆  Leaderboard", size=20, weight="bold",
               color=P["yellow"]).pack(side="left", padx=22)
        _btn(nav, "←  Back", lambda: self.app.show("MenuFrame"),
             width=100, height=34, fg="transparent", border=True,
             text_color=P["muted"], hover=P["surface"]).pack(side="right", padx=20)
        self.body = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.body.pack(fill="both", expand=True, padx=30, pady=20)


class HistoryFrame(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color=P["bg"])
        self.app = app
        self._build()

    def on_show(self):
        for w in self.body.winfo_children():
            w.destroy()
        rows = get_user_history(self.app.current_user["id"])
        if not rows:
            _label(self.body, "No history yet. Play your first quiz!",
                   size=14, color=P["muted"]).pack(pady=50)
            return

        for r in rows:
            pct = round(r["score"] / r["total"] * 100)
            col = P["green"] if pct >= 75 else P["yellow"] if pct >= 50 else P["red"]
            card = ctk.CTkFrame(self.body, fg_color=P["card"], corner_radius=10)
            card.pack(fill="x", pady=5)

            left = ctk.CTkFrame(card, fg_color="transparent")
            left.pack(side="left", padx=18, pady=12)
            _label(left, f"{r['score']}/{r['total']}  ({pct}%)",
                   size=18, weight="bold", color=col).pack(anchor="w")

            quiz_meta = r.get("quiz_name") or r.get("category") or "Test"
            code_meta = r.get("quiz_code") or "—"
            _label(left, f"{quiz_meta}  •  Code: {code_meta}  •  {r['time_taken']}s",
                   size=12, color=P["muted"]).pack(anchor="w", pady=(2, 0))

            _label(card, str(r["completed_at"] or "")[:16],
                   size=11, color=P["muted"]).pack(side="right", padx=18)

    def _build(self):
        nav = ctk.CTkFrame(self, fg_color=P["card"], corner_radius=0, height=62)
        nav.pack(fill="x")
        nav.pack_propagate(False)
        _label(nav, "📊  My History", size=20, weight="bold",
               color=P["cyan"]).pack(side="left", padx=22)
        _btn(nav, "←  Back", lambda: self.app.show("MenuFrame"),
             width=100, height=34, fg="transparent", border=True,
             text_color=P["muted"], hover=P["surface"]).pack(side="right", padx=20)
        self.body = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.body.pack(fill="both", expand=True, padx=30, pady=20)


class AdminFrame(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color=P["bg"])
        self.app = app
        self.categories = []
        self._build()

    def on_show(self):
        self.categories = get_categories()
        names = [c["name"] for c in self.categories]
        self.cat_opt.configure(values=names)
        if names:
            self.cat_opt.set(names[0])

    def _build(self):
        nav = ctk.CTkFrame(self, fg_color=P["card"], corner_radius=0, height=62)
        nav.pack(fill="x")
        nav.pack_propagate(False)
        _label(nav, "➕  Add Question", size=20, weight="bold",
               color=P["green"]).pack(side="left", padx=22)
        _btn(nav, "←  Back", lambda: self.app.show("MenuFrame"),
             width=100, height=34, fg="transparent", border=True,
             text_color=P["muted"], hover=P["surface"]).pack(side="right", padx=20)

        outer = ctk.CTkScrollableFrame(self, fg_color="transparent")
        outer.pack(fill="both", expand=True, padx=30, pady=20)
        card = ctk.CTkFrame(outer, fg_color=P["card"], corner_radius=16)
        card.pack(fill="x")

        _label(card, "Question Text", size=12, color=P["muted"]).pack(
            anchor="w", padx=22, pady=(20, 4))
        self.q_box = ctk.CTkTextbox(
            card, height=88, corner_radius=8,
            fg_color=P["surface"], border_color=P["border"],
            border_width=1, text_color=P["text"],
        )
        self.q_box.pack(fill="x", padx=22)

        row2 = ctk.CTkFrame(card, fg_color="transparent")
        row2.pack(fill="x", padx=22, pady=16)
        row2.columnconfigure((0, 1), weight=1)

        lf = ctk.CTkFrame(row2, fg_color="transparent")
        lf.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        _label(lf, "Category", size=12, color=P["muted"]).pack(anchor="w")
        self.cat_opt = ctk.CTkOptionMenu(
            lf, values=["Loading..."],
            fg_color=P["surface"], button_color=P["accent"],
            button_hover_color=P["accent2"], corner_radius=8, height=36,
            text_color=P["text"], dropdown_fg_color=P["card"],
        )
        self.cat_opt.pack(fill="x", pady=(4, 0))

        rf = ctk.CTkFrame(row2, fg_color="transparent")
        rf.grid(row=0, column=1, sticky="ew")
        _label(rf, "Difficulty", size=12, color=P["muted"]).pack(anchor="w")
        self.diff_opt = ctk.CTkOptionMenu(
            rf, values=["Easy", "Medium", "Hard"],
            fg_color=P["surface"], button_color=P["accent"],
            button_hover_color=P["accent2"], corner_radius=8, height=36,
            text_color=P["text"], dropdown_fg_color=P["card"],
        )
        self.diff_opt.pack(fill="x", pady=(4, 0))

        _label(card, "Answer Choices  —  select the correct one",
               size=12, color=P["muted"]).pack(anchor="w", padx=22, pady=(4, 8))

        self.correct_var = IntVar(value=0)
        self.choice_entries = []
        for i in range(4):
            r2 = ctk.CTkFrame(card, fg_color="transparent")
            r2.pack(fill="x", padx=22, pady=4)
            ctk.CTkRadioButton(
                r2, text="", variable=self.correct_var, value=i,
                radiobutton_width=18, radiobutton_height=18,
                fg_color=P["green"], hover_color=P["accent"],
            ).pack(side="left", padx=(0, 10))
            e = ctk.CTkEntry(
                r2, placeholder_text=f"Choice {i + 1}", height=38,
                corner_radius=8, fg_color=P["surface"],
                border_color=P["border"], border_width=1,
                text_color=P["text"],
            )
            e.pack(side="left", fill="x", expand=True)
            self.choice_entries.append(e)

        self.msg = _label(card, size=12)
        self.msg.pack(pady=10)
        _btn(card, "Add Question", self._submit, height=46,
             fg=P["green"], hover="#16a34a").pack(
            fill="x", padx=22, pady=(0, 22))

    def _submit(self):
        q       = self.q_box.get("1.0", "end").strip()
        choices = [e.get().strip() for e in self.choice_entries]
        if len(q) < 10:
            self.msg.configure(text="✗  Question must be 10+ characters.",
                               text_color=P["red"]); return
        if any(c == "" for c in choices):
            self.msg.configure(text="✗  Fill in all 4 choices.",
                               text_color=P["red"]); return
        if len(set(choices)) < 4:
            self.msg.configure(text="✗  Choices must be unique.",
                               text_color=P["red"]); return

        cat_name = self.cat_opt.get()
        cat_id   = next((c["id"] for c in self.categories if c["name"] == cat_name), None)
        add_question(q, cat_id, self.diff_opt.get(),
                     choices, self.correct_var.get())
        self.msg.configure(text="✓  Question added!", text_color=P["green"])
        self.q_box.delete("1.0", "end")
        for e in self.choice_entries:
            e.delete(0, "end")
        self.correct_var.set(0)


if __name__ == "__main__":
    App().mainloop()
