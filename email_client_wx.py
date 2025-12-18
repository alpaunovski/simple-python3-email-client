import wx
import os
from typing import Optional, Dict, List

import imaplib
import smtplib
import email
from email.header import decode_header


# ============================================================
# CONFIG MANAGEMENT (multiple accounts, stored in accounts.txt)
# ============================================================

CONFIG_FILE = "accounts.txt"


class AccountConfig:
    def __init__(
        self,
        name: str = "",
        email_addr: str = "",
        password: str = "",
        imap_server: str = "",
        imap_port: int = 993,
        smtp_server: str = "",
        smtp_port: int = 587,
    ):
        # The account name is used as a stable key in the accounts dictionary
        # and as the label in the Switch Account menu.
        self.name = name          # user-chosen account name (unique key)
        # Store credentials and server details for both IMAP and SMTP.
        self.email = email_addr
        self.password = password
        self.imap_server = imap_server
        self.imap_port = imap_port
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port

    def to_dict(self) -> Dict[str, str]:
        # Convert config values to a string-only dictionary suitable for file storage.
        return {
            "name": self.name,
            "email": self.email,
            "password": self.password,
            "imap_server": self.imap_server,
            "imap_port": str(self.imap_port),
            "smtp_server": self.smtp_server,
            "smtp_port": str(self.smtp_port),
        }

    @staticmethod
    def from_dict(d: Dict[str, str]) -> "AccountConfig":
        # Reconstruct an AccountConfig from key/value strings read from disk.
        return AccountConfig(
            name=d.get("name", ""),
            email_addr=d.get("email", ""),
            password=d.get("password", ""),
            imap_server=d.get("imap_server", ""),
            imap_port=int(d.get("imap_port", "993") or 993),
            smtp_server=d.get("smtp_server", ""),
            smtp_port=int(d.get("smtp_port", "587") or 587),
        )


def load_all_accounts() -> Dict[str, AccountConfig]:
    """Load all accounts from accounts.txt (simple INI-like format)."""
    if not os.path.exists(CONFIG_FILE):
        return {}

    accounts: Dict[str, AccountConfig] = {}
    current: Dict[str, str] = {}
    current_name: Optional[str] = None

    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            if line.startswith("[account ") and line.endswith("]"):
                # Save the previous account block before starting a new one.
                if current_name and current:
                    accounts[current_name] = AccountConfig.from_dict(current)

                current = {}
                # Extract account name from the section header.
                current_name = line[len("[account "):-1]
                current["name"] = current_name
            else:
                if "=" in line and current is not None:
                    key, value = line.split("=", 1)
                    current[key.strip()] = value.strip()

    if current_name and current:
        accounts[current_name] = AccountConfig.from_dict(current)

    return accounts


def save_all_accounts(accounts: Dict[str, AccountConfig]) -> None:
    """Save all accounts to accounts.txt."""
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        for acc in accounts.values():
            # Each account is written as its own section header.
            f.write(f"[account {acc.name}]\n")
            d = acc.to_dict()
            for key, val in d.items():
                if key == "name":
                    continue
                # Write key=value pairs in a simple INI-like format.
                f.write(f"{key}={val}\n")
            f.write("\n")


# ============================================================
# EMAIL HELPERS
# ============================================================

def _decode_mime_header(value: Optional[str]) -> str:
    if not value:
        return ""
    try:
        # Decode possibly-mixed encoded words per RFC 2047.
        decoded_fragments = decode_header(value)
        parts: List[str] = []
        for text, enc in decoded_fragments:
            if isinstance(text, bytes):
                try:
                    parts.append(text.decode(enc or "utf-8", errors="replace"))
                except Exception:
                    parts.append(text.decode("utf-8", errors="replace"))
            else:
                parts.append(text)
        return "".join(parts)
    except Exception:
        return value


def _extract_plain_text_body(msg) -> str:
    """Return a best-effort plain text body for an email.message.Message."""
    try:
        if msg.is_multipart():
            # Prefer text/plain parts to avoid HTML noise.
            for part in msg.walk():
                if part.get_content_type() == "text/plain":
                    payload = part.get_payload(decode=True) or b""
                    charset = part.get_content_charset() or "utf-8"
                    return payload.decode(charset, errors="replace")

            # Fallback to the first decodable part if no text/plain exists.
            for part in msg.walk():
                payload = part.get_payload(decode=True) or b""
                charset = part.get_content_charset() or "utf-8"
                return payload.decode(charset, errors="replace")

        else:
            # Single-part message: decode the payload directly.
            payload = msg.get_payload(decode=True) or b""
            charset = msg.get_content_charset() or "utf-8"
            return payload.decode(charset, errors="replace")
    except Exception:
        return "(Could not decode message body.)"


# ============================================================
# SETTINGS DIALOG (edit one AccountConfig)
# ============================================================

class SettingsDialog(wx.Dialog):
    def __init__(self, parent, account: AccountConfig, is_new: bool):
        title = "Add Account" if is_new else "Edit Active Account"
        super().__init__(parent, title=title, style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)

        self.account = account
        self.is_new = is_new

        main = wx.BoxSizer(wx.VERTICAL)

        grid = wx.FlexGridSizer(0, 2, 8, 8)
        grid.AddGrowableCol(1, 1)

        # Account name used for the display label and internal key.
        grid.Add(wx.StaticText(self, label="Account Name:"), 0, wx.ALIGN_RIGHT | wx.ALIGN_CENTER_VERTICAL)
        self.txt_name = wx.TextCtrl(self)
        self.txt_name.SetValue(account.name)
        grid.Add(self.txt_name, 1, wx.EXPAND)

        # Email address doubles as the IMAP/SMTP username.
        grid.Add(wx.StaticText(self, label="Email (username):"), 0, wx.ALIGN_RIGHT | wx.ALIGN_CENTER_VERTICAL)
        self.txt_email = wx.TextCtrl(self)
        self.txt_email.SetValue(account.email)
        grid.Add(self.txt_email, 1, wx.EXPAND)

        # Password is stored in plaintext for simplicity (no keychain integration).
        grid.Add(wx.StaticText(self, label="Password:"), 0, wx.ALIGN_RIGHT | wx.ALIGN_CENTER_VERTICAL)
        self.txt_password = wx.TextCtrl(self, style=wx.TE_PASSWORD)
        self.txt_password.SetValue(account.password)
        grid.Add(self.txt_password, 1, wx.EXPAND)

        # IMAP server hosts the inbox for reading.
        grid.Add(wx.StaticText(self, label="IMAP server:"), 0, wx.ALIGN_RIGHT | wx.ALIGN_CENTER_VERTICAL)
        self.txt_imap_server = wx.TextCtrl(self)
        self.txt_imap_server.SetValue(account.imap_server)
        grid.Add(self.txt_imap_server, 1, wx.EXPAND)

        # IMAP port: typically 993 for SSL, 143 for plain/TLS.
        grid.Add(wx.StaticText(self, label="IMAP port:"), 0, wx.ALIGN_RIGHT | wx.ALIGN_CENTER_VERTICAL)
        self.txt_imap_port = wx.TextCtrl(self)
        self.txt_imap_port.SetValue(str(account.imap_port))
        grid.Add(self.txt_imap_port, 1, wx.EXPAND)

        # SMTP server is used for sending messages.
        grid.Add(wx.StaticText(self, label="SMTP server:"), 0, wx.ALIGN_RIGHT | wx.ALIGN_CENTER_VERTICAL)
        self.txt_smtp_server = wx.TextCtrl(self)
        self.txt_smtp_server.SetValue(account.smtp_server)
        grid.Add(self.txt_smtp_server, 1, wx.EXPAND)

        # SMTP port: typically 587 for STARTTLS, 465 for SSL.
        grid.Add(wx.StaticText(self, label="SMTP port:"), 0, wx.ALIGN_RIGHT | wx.ALIGN_CENTER_VERTICAL)
        self.txt_smtp_port = wx.TextCtrl(self)
        self.txt_smtp_port.SetValue(str(account.smtp_port))
        grid.Add(self.txt_smtp_port, 1, wx.EXPAND)

        main.Add(grid, 1, wx.EXPAND | wx.ALL, 10)

        btn_sizer = wx.StdDialogButtonSizer()
        ok_btn = wx.Button(self, wx.ID_OK, "Save")
        cancel_btn = wx.Button(self, wx.ID_CANCEL)
        btn_sizer.Add(ok_btn)
        btn_sizer.Add(cancel_btn)
        btn_sizer.Realize()

        main.Add(btn_sizer, 0, wx.EXPAND | wx.ALL, 10)

        self.SetSizer(main)
        main.Fit(self)

        ok_btn.Bind(wx.EVT_BUTTON, self.on_save)

    def on_save(self, event):
        # Validate required fields before committing changes.
        name = self.txt_name.GetValue().strip()
        if not name:
            wx.MessageBox("Account name cannot be empty.", "Error", wx.OK | wx.ICON_ERROR)
            return

        email_addr = self.txt_email.GetValue().strip()
        if not email_addr:
            wx.MessageBox("Email cannot be empty.", "Error", wx.OK | wx.ICON_ERROR)
            return

        try:
            # Port values are typed as integers in AccountConfig.
            imap_port = int(self.txt_imap_port.GetValue().strip())
            smtp_port = int(self.txt_smtp_port.GetValue().strip())
        except ValueError:
            wx.MessageBox("IMAP and SMTP ports must be integers.", "Error", wx.OK | wx.ICON_ERROR)
            return

        # Persist changes back to the provided AccountConfig instance.
        self.account.name = name
        self.account.email = email_addr
        self.account.password = self.txt_password.GetValue()
        self.account.imap_server = self.txt_imap_server.GetValue().strip()
        self.account.imap_port = imap_port
        self.account.smtp_server = self.txt_smtp_server.GetValue().strip()
        self.account.smtp_port = smtp_port

        self.EndModal(wx.ID_OK)


# ============================================================
# COMPOSE DIALOG
# ============================================================

class ComposeDialog(wx.Dialog):
    def __init__(self, parent, from_addr: str):
        super().__init__(parent, title="Compose Email", style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)

        self.from_addr = from_addr

        main = wx.BoxSizer(wx.VERTICAL)

        grid = wx.FlexGridSizer(0, 2, 5, 5)
        grid.AddGrowableCol(1, 1)

        grid.Add(wx.StaticText(self, label="From:"), 0, wx.ALIGN_RIGHT | wx.ALIGN_CENTER_VERTICAL)
        grid.Add(wx.StaticText(self, label=from_addr), 1, wx.EXPAND | wx.ALIGN_CENTER_VERTICAL)

        # Recipient(s) can be a comma-separated list.
        grid.Add(wx.StaticText(self, label="To:"), 0, wx.ALIGN_RIGHT | wx.ALIGN_CENTER_VERTICAL)
        self.txt_to = wx.TextCtrl(self)
        grid.Add(self.txt_to, 1, wx.EXPAND)

        grid.Add(wx.StaticText(self, label="Subject:"), 0, wx.ALIGN_RIGHT | wx.ALIGN_CENTER_VERTICAL)
        self.txt_subject = wx.TextCtrl(self)
        grid.Add(self.txt_subject, 1, wx.EXPAND)

        main.Add(grid, 0, wx.EXPAND | wx.ALL, 10)

        # Large multiline editor for the message body.
        self.txt_body = wx.TextCtrl(self, style=wx.TE_MULTILINE | wx.BORDER_SUNKEN, size=(600, 300))
        main.Add(self.txt_body, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)

        btn_sizer = wx.StdDialogButtonSizer()
        send_btn = wx.Button(self, wx.ID_OK, "Send")
        cancel_btn = wx.Button(self, wx.ID_CANCEL)
        btn_sizer.Add(send_btn)
        btn_sizer.Add(cancel_btn)
        btn_sizer.Realize()

        main.Add(btn_sizer, 0, wx.EXPAND | wx.ALL, 10)

        self.SetSizer(main)
        main.Fit(self)

    def get_values(self):
        # Extract final user-entered values, trimming address whitespace.
        return (
            self.txt_to.GetValue().strip(),
            self.txt_subject.GetValue(),
            self.txt_body.GetValue(),
        )


# ============================================================
# MAIN APPLICATION FRAME
# ============================================================

class EmailClientFrame(wx.Frame):
    def __init__(self):
        super().__init__(None, title="Simple Python Email Client (Multiple Accounts)", size=(900, 600))
        self.Centre()

        # Load known accounts from disk and choose a default active account.
        self.accounts: Dict[str, AccountConfig] = load_all_accounts()
        self.active_account: Optional[AccountConfig] = None

        if self.accounts:
            # Pick first account as active
            first_name = sorted(self.accounts.keys())[0]
            self.active_account = self.accounts[first_name]

        # List of parsed message dictionaries for the active mailbox view.
        self.messages: List[Dict] = []

        self.panel = wx.Panel(self)

        self._create_menu()
        self._create_layout()

    # ------------------------------
    # MENU
    # ------------------------------
    def _create_menu(self):
        menubar = wx.MenuBar()
        file_menu = wx.Menu()

        # Account management actions.
        self.menu_item_add_account = file_menu.Append(wx.ID_ANY, "Add Account…")
        self.menu_item_switch_root = file_menu.AppendSubMenu(wx.Menu(), "Switch Account")
        self.switch_acc_parent_item = self.menu_item_switch_root
        self.switch_acc_menu: wx.Menu = self.menu_item_switch_root.GetSubMenu()

        self.menu_item_delete_account = file_menu.Append(wx.ID_ANY, "Delete Account…")
        file_menu.AppendSeparator()
        self.menu_item_edit_active = file_menu.Append(wx.ID_ANY, "Settings / Edit Active Account")
        file_menu.AppendSeparator()
        exit_item = file_menu.Append(wx.ID_EXIT, "Exit")

        menubar.Append(file_menu, "&File")
        self.SetMenuBar(menubar)

        self.Bind(wx.EVT_MENU, self.on_add_account, self.menu_item_add_account)
        self.Bind(wx.EVT_MENU, self.on_delete_account, self.menu_item_delete_account)
        self.Bind(wx.EVT_MENU, self.on_edit_active_account, self.menu_item_edit_active)
        self.Bind(wx.EVT_MENU, lambda evt: self.Close(), exit_item)

        self._rebuild_switch_account_menu()

    def _rebuild_switch_account_menu(self):
        # Replace submenu with a fresh one each time
        if hasattr(self, "switch_acc_menu") and self.switch_acc_menu is not None:
            # Detach old submenu and destroy it
            self.switch_acc_parent_item.SetSubMenu(None)
            self.switch_acc_menu.Destroy()

        self.switch_acc_menu = wx.Menu()
        self.switch_acc_parent_item.SetSubMenu(self.switch_acc_menu)

        if not self.accounts:
            # Show a disabled placeholder when no accounts exist.
            disabled_item = self.switch_acc_menu.Append(wx.ID_ANY, "(no accounts)")
            disabled_item.Enable(False)
            return

        for name in sorted(self.accounts.keys()):
            item = self.switch_acc_menu.Append(wx.ID_ANY, name)
            # capture name in default argument
            self.Bind(wx.EVT_MENU, lambda evt, n=name: self.on_switch_account(n), item)

    # ------------------------------
    # LAYOUT
    # ------------------------------
    def _create_layout(self):
        main_sizer = wx.BoxSizer(wx.HORIZONTAL)

        # Left side: toolbar and email list.
        left_sizer = wx.BoxSizer(wx.VERTICAL)
        top_buttons = wx.BoxSizer(wx.HORIZONTAL)

        self.btn_refresh = wx.Button(self.panel, label="Refresh")
        self.btn_compose = wx.Button(self.panel, label="Compose")
        top_buttons.Add(self.btn_refresh, 0, wx.ALL, 5)
        top_buttons.Add(self.btn_compose, 0, wx.ALL, 5)

        left_sizer.Add(top_buttons, 0)

        self.email_list = wx.ListCtrl(
            self.panel,
            style=wx.LC_REPORT | wx.BORDER_SUNKEN | wx.LC_SINGLE_SEL
        )
        self.email_list.InsertColumn(0, "Subject", width=260)
        left_sizer.Add(self.email_list, 1, wx.EXPAND | wx.ALL, 5)

        # Right side: header info and body viewer.
        right_sizer = wx.BoxSizer(wx.VERTICAL)

        header = wx.FlexGridSizer(3, 2, 5, 5)
        header.AddGrowableCol(1, 1)

        self.lbl_from_value = wx.StaticText(self.panel, label="(select email)")
        self.lbl_to_value = wx.StaticText(self.panel, label="-")
        self.lbl_subject_value = wx.StaticText(self.panel, label="-")

        header.Add(wx.StaticText(self.panel, label="From:"))
        header.Add(self.lbl_from_value, 1, wx.EXPAND)
        header.Add(wx.StaticText(self.panel, label="To:"))
        header.Add(self.lbl_to_value, 1, wx.EXPAND)
        header.Add(wx.StaticText(self.panel, label="Subject:"))
        header.Add(self.lbl_subject_value, 1, wx.EXPAND)

        right_sizer.Add(header, 0, wx.EXPAND | wx.ALL, 8)

        self.body_text = wx.TextCtrl(
            self.panel,
            style=wx.TE_MULTILINE | wx.TE_READONLY | wx.BORDER_SUNKEN
        )
        if self.active_account:
            # Provide a hint when an account is selected but emails are not loaded yet.
            start_msg = "Use Refresh to load emails for the active account."
        else:
            # Provide a hint when no account exists yet.
            start_msg = "Add an account from File → Add Account…"
        self.body_text.SetValue(start_msg)

        right_sizer.Add(self.body_text, 1, wx.EXPAND | wx.ALL, 8)

        main_sizer.Add(left_sizer, 1, wx.EXPAND)
        main_sizer.Add(right_sizer, 2, wx.EXPAND)

        self.panel.SetSizer(main_sizer)

        # Bind UI events to handlers.
        self.btn_refresh.Bind(wx.EVT_BUTTON, self.on_refresh)
        self.btn_compose.Bind(wx.EVT_BUTTON, self.on_compose)
        self.email_list.Bind(wx.EVT_LIST_ITEM_SELECTED, self.on_select_email)

    # ============================================================
    # ACCOUNT OPERATIONS
    # ============================================================
    def on_add_account(self, event):
        # Open a dialog to collect account details.
        new_acc = AccountConfig()
        dlg = SettingsDialog(self, new_acc, is_new=True)
        if dlg.ShowModal() == wx.ID_OK:
            if not new_acc.name:
                wx.MessageBox("Account name cannot be empty.", "Error", wx.OK | wx.ICON_ERROR)
            elif new_acc.name in self.accounts:
                wx.MessageBox("An account with this name already exists.", "Error", wx.OK | wx.ICON_ERROR)
            else:
                self.accounts[new_acc.name] = new_acc
                save_all_accounts(self.accounts)
                self._rebuild_switch_account_menu()
                if self.active_account is None:
                    # If there was no active account, use the new one.
                    self.active_account = new_acc
                    self.body_text.SetValue("New account added. Use Refresh to load emails.")
        dlg.Destroy()

    def on_delete_account(self, event):
        if not self.accounts:
            wx.MessageBox("No accounts to delete.", "Delete Account", wx.OK | wx.ICON_INFORMATION)
            return

        names = sorted(self.accounts.keys())
        dlg = wx.SingleChoiceDialog(self, "Select an account to delete:", "Delete Account", names)
        if dlg.ShowModal() == wx.ID_OK:
            selected = dlg.GetStringSelection()
            if selected in self.accounts:
                if (self.active_account is not None) and (self.active_account.name == selected):
                    # Deleting current active account
                    self.active_account = None
                    self.messages.clear()
                    self.email_list.DeleteAllItems()
                    self.lbl_from_value.SetLabel("(select email)")
                    self.lbl_to_value.SetLabel("-")
                    self.lbl_subject_value.SetLabel("-")
                    self.body_text.SetValue("Active account deleted. Add or switch to another account.")
                # Remove account from memory and persist updated list.
                del self.accounts[selected]
                save_all_accounts(self.accounts)
                self._rebuild_switch_account_menu()
        dlg.Destroy()

    def on_switch_account(self, account_name: str):
        # Swap the active account and clear any loaded messages.
        if account_name not in self.accounts:
            wx.MessageBox("Account not found.", "Switch Account", wx.OK | wx.ICON_ERROR)
            return
        self.active_account = self.accounts[account_name]
        self.messages.clear()
        self.email_list.DeleteAllItems()
        self.lbl_from_value.SetLabel("(select email)")
        self.lbl_to_value.SetLabel("-")
        self.lbl_subject_value.SetLabel("-")
        self.body_text.SetValue(f"Switched to account '{account_name}'. Click Refresh to load emails.")

    def on_edit_active_account(self, event):
        if not self.active_account:
            wx.MessageBox("No active account to edit.", "Edit Account", wx.OK | wx.ICON_INFORMATION)
            return

        old_name = self.active_account.name
        dlg = SettingsDialog(self, self.active_account, is_new=False)
        if dlg.ShowModal() == wx.ID_OK:
            new_name = self.active_account.name or old_name

            # If the name changed, handle dictionary key move
            if new_name != old_name:
                if new_name in self.accounts and self.accounts[new_name] is not self.active_account:
                    wx.MessageBox("Another account already uses that name. Keeping old name.", "Error")
                    self.active_account.name = old_name
                else:
                    # Replace the dictionary key to reflect the new account name.
                    del self.accounts[old_name]
                    self.accounts[new_name] = self.active_account

            save_all_accounts(self.accounts)
            self._rebuild_switch_account_menu()
        dlg.Destroy()

    # ============================================================
    # IMAP FETCH
    # ============================================================
    def on_refresh(self, event):
        if not self.active_account:
            wx.MessageBox("No active account. Add one from File → Add Account…", "Refresh", wx.OK | wx.ICON_INFORMATION)
            return

        acc = self.active_account
        try:
            # Give the user immediate feedback before network work.
            self.body_text.SetValue("Loading emails from server...\n")
            wx.GetApp().Yield()

            # Connect
            if acc.imap_port == 993:
                # Port 993 is implicit SSL.
                imap = imaplib.IMAP4_SSL(acc.imap_server, acc.imap_port)
            else:
                # For non-SSL ports, attempt STARTTLS if supported.
                imap = imaplib.IMAP4(acc.imap_server, acc.imap_port)
                try:
                    imap.starttls()
                except Exception:
                    pass

            imap.login(acc.email, acc.password)

            status, _ = imap.select("INBOX")
            if status != "OK":
                raise RuntimeError("Could not open INBOX")

            status, data = imap.search(None, "ALL")
            if status != "OK":
                raise RuntimeError("Search failed")

            ids = data[0].split()
            if not ids:
                # Empty inbox: clear the UI and stop early.
                self.messages.clear()
                self.email_list.DeleteAllItems()
                self.body_text.SetValue("INBOX is empty.")
                imap.close()
                imap.logout()
                return

            # Limit to the most recent 20 messages for faster UI updates.
            latest_ids = ids[-20:]  # last 20
            self.messages = []
            self.email_list.DeleteAllItems()

            # Newest first so the top of the list is the latest email.
            for msg_id in reversed(latest_ids):
                status, msg_data = imap.fetch(msg_id, "(RFC822)")
                if status != "OK" or not msg_data or msg_data[0] is None:
                    continue
                raw = msg_data[0][1]
                msg = email.message_from_bytes(raw)

                # Decode headers and body into display-friendly strings.
                subj = _decode_mime_header(msg.get("Subject")) or "(no subject)"
                from_ = _decode_mime_header(msg.get("From")) or ""
                to_ = _decode_mime_header(msg.get("To")) or ""
                body = _extract_plain_text_body(msg)

                # Store message metadata for later display.
                self.messages.append(
                    {"id": msg_id, "subject": subj, "from": from_, "to": to_, "body": body}
                )
                self.email_list.InsertItem(self.email_list.GetItemCount(), subj)

            self.body_text.SetValue("Emails loaded. Select one on the left.")
            imap.close()
            imap.logout()

        except imaplib.IMAP4.error as e:
            # IMAP errors usually indicate auth or server issues.
            wx.MessageBox(f"IMAP error:\n{e}", "IMAP Error", wx.OK | wx.ICON_ERROR)
        except Exception as e:
            wx.MessageBox(f"Error while fetching emails:\n{e}", "Error", wx.OK | wx.ICON_ERROR)

    # ============================================================
    # EMAIL VIEW
    # ============================================================
    def on_select_email(self, event):
        # Update the preview pane to match the selected email row.
        idx = event.GetIndex()
        if idx < 0 or idx >= len(self.messages):
            return
        msg = self.messages[idx]
        self.lbl_from_value.SetLabel(msg["from"])
        self.lbl_to_value.SetLabel(msg["to"])
        self.lbl_subject_value.SetLabel(msg["subject"])
        self.body_text.SetValue(msg["body"])

    # ============================================================
    # SMTP SEND
    # ============================================================
    def on_compose(self, event):
        if not self.active_account:
            wx.MessageBox("No active account. Add one from File → Add Account…", "Compose", wx.OK | wx.ICON_INFORMATION)
            return

        acc = self.active_account
        dlg = ComposeDialog(self, acc.email)
        if dlg.ShowModal() == wx.ID_OK:
            to_addr, subject, body = dlg.get_values()
            if not to_addr:
                wx.MessageBox("Please enter at least one recipient.", "Error", wx.OK | wx.ICON_ERROR)
                dlg.Destroy()
                return

            # Split comma-separated recipients and drop empties.
            recipients = [a.strip() for a in to_addr.split(",") if a.strip()]
            if not recipients:
                wx.MessageBox("No valid recipients found.", "Error", wx.OK | wx.ICON_ERROR)
                dlg.Destroy()
                return

            try:
                # Build a minimal RFC 5322 message with headers and body.
                msg_lines = [
                    f"From: {acc.email}",
                    f"To: {', '.join(recipients)}",
                    f"Subject: {subject}",
                    "",
                    body,
                ]
                msg_str = "\r\n".join(msg_lines)

                if acc.smtp_port == 465:
                    # Port 465 uses implicit SSL.
                    server = smtplib.SMTP_SSL(acc.smtp_server, acc.smtp_port)
                else:
                    # For other ports, attempt STARTTLS if available.
                    server = smtplib.SMTP(acc.smtp_server, acc.smtp_port)
                    try:
                        server.starttls()
                    except Exception:
                        pass

                server.login(acc.email, acc.password)
                server.sendmail(acc.email, recipients, msg_str)
                server.quit()

                wx.MessageBox("Email sent successfully.", "Compose", wx.OK | wx.ICON_INFORMATION)
            except Exception as e:
                wx.MessageBox(f"SMTP error:\n{e}", "SMTP Error", wx.OK | wx.ICON_ERROR)

        dlg.Destroy()


# ============================================================
# APP START
# ============================================================

class EmailApp(wx.App):
    def OnInit(self):
        # Initialize the main frame and start the wx event loop.
        frame = EmailClientFrame()
        frame.Show()
        return True


if __name__ == "__main__":
    app = EmailApp(False)
    app.MainLoop()
