/**
 * Finance Tracker — shared UI: mobile sidebar, client-side validation, expense edit helper.
 */
(function () {
  function $(sel, root) {
    return (root || document).querySelector(sel);
  }

  function $all(sel, root) {
    return Array.prototype.slice.call((root || document).querySelectorAll(sel));
  }

  function todayISODate() {
    var d = new Date();
    var m = String(d.getMonth() + 1).padStart(2, "0");
    var day = String(d.getDate()).padStart(2, "0");
    return d.getFullYear() + "-" + m + "-" + day;
  }

  function setDefaultDates() {
    $all('input[type="date"]').forEach(function (input) {
      if (!input.value) {
        input.value = todayISODate();
      }
    });
  }

  /* --- Mobile sidebar --- */
  function initSidebar() {
    var toggle = $("#sidebarToggle");
    var sidebar = $("#sidebar");
    var overlay = $("#sidebarOverlay");
    if (!toggle || !sidebar) return;

    function openNav() {
      sidebar.classList.add("is-open");
      if (overlay) overlay.hidden = false;
      toggle.setAttribute("aria-expanded", "true");
    }

    function closeNav() {
      sidebar.classList.remove("is-open");
      if (overlay) overlay.hidden = true;
      toggle.setAttribute("aria-expanded", "false");
    }

    toggle.addEventListener("click", function () {
      if (sidebar.classList.contains("is-open")) closeNav();
      else openNav();
    });

    if (overlay) {
      overlay.addEventListener("click", closeNav);
    }

    window.addEventListener("resize", function () {
      if (window.innerWidth > 900) closeNav();
    });
  }

  /* --- Flash auto-dismiss --- */
  function initFlash() {
    $all(".flash").forEach(function (el) {
      window.setTimeout(function () {
        el.style.opacity = "0";
        el.style.transform = "translateY(-4px)";
        window.setTimeout(function () {
          if (el.parentNode) el.parentNode.removeChild(el);
        }, 300);
      }, 5200);
    });
  }

  /* --- Forms: show field error --- */
  function showError(fieldName, message, form) {
    var el = form.querySelector('[data-error-for="' + fieldName + '"]');
    if (!el) return;
    el.textContent = message;
    el.hidden = !message;
  }

  function clearErrors(form) {
    $all(".field__error", form).forEach(function (el) {
      el.textContent = "";
      el.hidden = true;
    });
  }

  function attachLoginValidation() {
    var form = $("#loginForm");
    if (!form) return;
    form.addEventListener("submit", function (e) {
      clearErrors(form);
      var ok = true;
      var u = form.username.value.trim();
      var p = form.password.value;
      if (u.length < 2) {
        showError("username", "Enter your username.", form);
        ok = false;
      }
      if (!p) {
        showError("password", "Enter your password.", form);
        ok = false;
      }
      if (!ok) e.preventDefault();
    });
  }

  function attachRegisterValidation() {
    var form = $("#registerForm");
    if (!form) return;
    form.addEventListener("submit", function (e) {
      clearErrors(form);
      var ok = true;
      var u = form.username.value.trim();
      var email = form.email.value.trim();
      var p = form.password.value;
      var c = form.confirm_password.value;

      if (u.length < 3) {
        showError("username", "Username must be at least 3 characters.", form);
        ok = false;
      }
      if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
        showError("email", "Enter a valid email address.", form);
        ok = false;
      }
      if (p.length < 8) {
        showError("password", "Password must be at least 8 characters.", form);
        ok = false;
      }
      if (p !== c) {
        showError("confirm_password", "Passwords do not match.", form);
        ok = false;
      }
      if (!ok) e.preventDefault();
    });
  }

  function attachExpenseValidation() {
    var form = $("#expenseForm");
    if (!form) return;
    form.addEventListener("submit", function (e) {
      clearErrors(form);
      var ok = true;
      var title = form.title.value.trim();
      var amount = parseFloat(form.amount.value);
      if (!title) {
        showError("title", "Title is required.", form);
        ok = false;
      }
      if (!(amount > 0)) {
        showError("amount", "Enter a positive amount.", form);
        ok = false;
      }
      if (!ok) e.preventDefault();
    });
  }

  function attachIncomeValidation() {
    var form = $("#incomeForm");
    if (!form) return;
    form.addEventListener("submit", function (e) {
      clearErrors(form);
      var ok = true;
      var source = form.source.value.trim();
      var amount = parseFloat(form.amount.value);
      if (!source) {
        showError("source", "Source is required.", form);
        ok = false;
      }
      if (!(amount > 0)) {
        showError("amount", "Enter a positive amount.", form);
        ok = false;
      }
      if (!ok) e.preventDefault();
    });
  }

  /* --- Expense row → edit form --- */
  function initExpenseEdit() {
    var editForm = $("#expenseEditForm");
    var hint = $("#editExpenseHint");
    var cancel = $("#cancelEditExpense");
    if (!editForm) return;

    function fillEdit(row) {
      $("#edit_expense_id", editForm).value = row.dataset.expenseId || "";
      $("#edit_title", editForm).value = row.dataset.title || "";
      $("#edit_amount", editForm).value = row.dataset.amount || "";
      $("#edit_expense_date", editForm).value = row.dataset.date || "";
      var cat = row.dataset.category || "Other";
      var sel = $("#edit_category", editForm);
      if (sel) sel.value = cat;
      editForm.hidden = false;
      if (hint) hint.hidden = true;
      editForm.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }

    function resetEdit() {
      editForm.hidden = true;
      if (hint) hint.hidden = false;
    }

    $all(".js-edit-expense").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var tr = btn.closest("tr");
        if (tr) fillEdit(tr);
      });
    });

    if (cancel) cancel.addEventListener("click", resetEdit);
  }

  document.addEventListener("DOMContentLoaded", function () {
    setDefaultDates();
    initSidebar();
    initFlash();
    attachLoginValidation();
    attachRegisterValidation();
    attachExpenseValidation();
    attachIncomeValidation();
    initExpenseEdit();
  });
})();
