// Live checks for the registration form. The server repeats every rule.
(function () {
  var form = document.querySelector('form[data-validate="register"]');
  if (!form) return;

  var usernameRe = /^[A-Za-z]+$/;
  var emailRe = /^[A-Za-z0-9._%+-]+@gmail\.com$/;

  var rules = {
    length: function (p) { return p.length >= 8; },
    upper: function (p) { return /[A-Z]/.test(p); },
    lower: function (p) { return /[a-z]/.test(p); },
    number: function (p) { return /\d/.test(p); },
    special: function (p) { return /[^A-Za-z0-9]/.test(p); }
  };

  function setError(name, message) {
    var el = form.querySelector('[data-error-for="' + name + '"]');
    if (el) el.textContent = message;
  }

  function updatePasswordRules() {
    var value = form.password.value;
    var allOk = true;
    Object.keys(rules).forEach(function (key) {
      var ok = rules[key](value);
      form.querySelector('[data-rule="' + key + '"]').classList.toggle('ok', ok);
      if (!ok) allOk = false;
    });
    return allOk;
  }

  form.username.addEventListener('input', function () {
    var v = form.username.value;
    setError('username', v && !usernameRe.test(v) ? 'Use letters only (A-Z, a-z). No numbers, spaces or symbols.' : '');
  });

  form.email.addEventListener('input', function () {
    var v = form.email.value;
    setError('email', v && !emailRe.test(v) ? 'Email must end with @gmail.com.' : '');
  });

  form.password.addEventListener('input', updatePasswordRules);

  form.confirm.addEventListener('input', function () {
    setError('confirm', form.confirm.value && form.confirm.value !== form.password.value ? 'Passwords do not match.' : '');
  });

  form.addEventListener('submit', function (event) {
    var problems = false;
    if (!form.name.value.trim()) { setError('name', 'Enter your full name.'); problems = true; }
    if (!usernameRe.test(form.username.value)) { setError('username', 'Use letters only (A-Z, a-z). No numbers, spaces or symbols.'); problems = true; }
    if (!emailRe.test(form.email.value)) { setError('email', 'Email must end with @gmail.com.'); problems = true; }
    if (!updatePasswordRules()) { setError('password', 'Password does not meet all the rules below.'); problems = true; }
    if (form.password.value !== form.confirm.value) { setError('confirm', 'Passwords do not match.'); problems = true; }
    if (form.verification && !form.verification.value) { setError('verification', 'Enter the teacher verification password.'); problems = true; }
    if (problems) event.preventDefault();
  });

  updatePasswordRules();
})();
