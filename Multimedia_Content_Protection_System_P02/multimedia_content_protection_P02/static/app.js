function askPassword(action, title, confirmDelete=false) {
  if (confirmDelete && !confirm("Permanently delete this protected document?")) return;
  const password = prompt(title + "\\nEnter your account password:");
  if (password === null) return;
  if (!password) { alert("Password is required."); return; }
  const form = document.getElementById("secureActionForm");
  form.action = action;
  document.getElementById("actionPassword").value = password;
  form.submit();
}
