/**
 * Кастомный JavaScript для Django Jazzmin Admin Panel
 * Поддержка переключения светлой/тёмной темы
 */

document.addEventListener("DOMContentLoaded", () => {
  // Создаём кнопку переключения темы
  createThemeToggle()

  // Применяем сохранённую тему
  applySavedTheme()
})

/**
 * Создаёт кнопку переключения темы
 */
function createThemeToggle() {
  const toggle = document.createElement("button")
  toggle.className = "theme-toggle"
  toggle.id = "theme-toggle"
  toggle.title = "Переключить тему"
  toggle.innerHTML = '<i class="fas fa-moon"></i>'

  toggle.addEventListener("click", toggleTheme)

  document.body.appendChild(toggle)
}

/**
 * Переключает между светлой и тёмной темой
 */
function toggleTheme() {
  const body = document.body
  const toggle = document.getElementById("theme-toggle")
  const isLight = body.classList.contains("light-mode")

  if (isLight) {
    // Переключаем на тёмную
    body.classList.remove("light-mode")
    body.setAttribute("data-theme", "dark")
    toggle.innerHTML = '<i class="fas fa-moon"></i>'
    localStorage.setItem("admin-theme", "dark")

    // Обновляем Bootstrap тему если используется
    updateBootstrapTheme("dark")
  } else {
    // Переключаем на светлую
    body.classList.add("light-mode")
    body.setAttribute("data-theme", "light")
    toggle.innerHTML = '<i class="fas fa-sun"></i>'
    localStorage.setItem("admin-theme", "light")

    // Обновляем Bootstrap тему если используется
    updateBootstrapTheme("light")
  }
}

/**
 * Применяет сохранённую тему при загрузке
 */
function applySavedTheme() {
  const savedTheme = localStorage.getItem("admin-theme") || "dark"
  const body = document.body
  const toggle = document.getElementById("theme-toggle")

  if (savedTheme === "light") {
    body.classList.add("light-mode")
    body.setAttribute("data-theme", "light")
    if (toggle) {
      toggle.innerHTML = '<i class="fas fa-sun"></i>'
    }
    updateBootstrapTheme("light")
  } else {
    body.classList.remove("light-mode")
    body.setAttribute("data-theme", "dark")
    if (toggle) {
      toggle.innerHTML = '<i class="fas fa-moon"></i>'
    }
    updateBootstrapTheme("dark")
  }
}

/**
 * Обновляет Bootstrap/AdminLTE классы темы
 */
function updateBootstrapTheme(theme) {
  const navbar = document.querySelector(".main-header.navbar")
  const sidebar = document.querySelector(".main-sidebar")

  if (theme === "light") {
    // Светлая тема
    if (navbar) {
      navbar.classList.remove("navbar-dark")
      navbar.classList.add("navbar-light")
    }
    if (sidebar) {
      sidebar.classList.remove("sidebar-dark-warning")
      sidebar.classList.add("sidebar-light-warning")
    }
  } else {
    // Тёмная тема
    if (navbar) {
      navbar.classList.remove("navbar-light")
      navbar.classList.add("navbar-dark")
    }
    if (sidebar) {
      sidebar.classList.remove("sidebar-light-warning")
      sidebar.classList.add("sidebar-dark-warning")
    }
  }
}

/**
 * Утилита для показа уведомлений
 */
function showNotification(message, type = "info") {
  const alertDiv = document.createElement("div")
  alertDiv.className = `alert alert-${type} alert-dismissible fade show`
  alertDiv.style.cssText = "position: fixed; top: 70px; right: 20px; z-index: 9999; min-width: 300px;"
  alertDiv.innerHTML = `
        ${message}
        <button type="button" class="close" data-dismiss="alert" aria-label="Close">
            <span aria-hidden="true">&times;</span>
        </button>
    `

  document.body.appendChild(alertDiv)

  // Автоматически скрываем через 5 секунд
  setTimeout(() => {
    alertDiv.remove()
  }, 5000)
}
