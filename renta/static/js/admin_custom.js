/**
 * Кастомный JavaScript для Django Jazzmin Admin Panel
 * ООО "ИНТЕРЬЕР" - Поддержка переключения светлой/тёмной темы
 * Версия 2.0
 */

document.addEventListener("DOMContentLoaded", () => {
  // Создаём кнопку переключения темы
  createThemeToggle()

  // Применяем сохранённую тему
  applySavedTheme()

  // Добавляем анимации при загрузке
  addLoadAnimations()
})

/**
 * Создаёт кнопку переключения темы
 */
function createThemeToggle() {
  // Проверяем, не создана ли уже кнопка
  if (document.getElementById("theme-toggle")) return

  const toggle = document.createElement("button")
  toggle.className = "theme-toggle"
  toggle.id = "theme-toggle"
  toggle.title = "Переключить тему"
  toggle.setAttribute("aria-label", "Переключить тему")
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

  // Добавляем класс для анимации
  body.classList.add("theme-transitioning")

  if (isLight) {
    // Переключаем на тёмную
    body.classList.remove("light-mode")
    body.setAttribute("data-theme", "dark")
    if (toggle) {
      toggle.innerHTML = '<i class="fas fa-moon"></i>'
    }
    localStorage.setItem("admin-theme", "dark")
    updateBootstrapTheme("dark")
  } else {
    // Переключаем на светлую
    body.classList.add("light-mode")
    body.setAttribute("data-theme", "light")
    if (toggle) {
      toggle.innerHTML = '<i class="fas fa-sun"></i>'
    }
    localStorage.setItem("admin-theme", "light")
    updateBootstrapTheme("light")
  }

  // Убираем класс анимации после завершения
  setTimeout(() => {
    body.classList.remove("theme-transitioning")
  }, 400)
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
  const wrapper = document.querySelector(".wrapper")

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
 * Добавляет анимации при загрузке страницы
 */
function addLoadAnimations() {
  // Анимируем карточки
  const cards = document.querySelectorAll(".card, .info-box, .small-box, .stat-card, .chart-card, .data-card")
  cards.forEach((card, index) => {
    card.style.opacity = "0"
    card.style.transform = "translateY(20px)"
    setTimeout(
      () => {
        card.style.transition = "opacity 0.4s ease, transform 0.4s ease"
        card.style.opacity = "1"
        card.style.transform = "translateY(0)"
      },
      50 + index * 50,
    )
  })
}

/**
 * Утилита для показа уведомлений
 */
function showNotification(message, type = "info") {
  const alertDiv = document.createElement("div")
  const typeClass = type === "error" ? "danger" : type === "success" ? "success" : "info"

  alertDiv.className = `alert alert-${typeClass} alert-dismissible fade show`
  alertDiv.style.cssText = `
        position: fixed;
        top: 80px;
        right: 20px;
        z-index: 9999;
        min-width: 300px;
        max-width: 450px;
        border-radius: 10px;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
        animation: slideInRight 0.3s ease;
    `

  const iconClass =
    type === "error" ? "fa-exclamation-circle" : type === "success" ? "fa-check-circle" : "fa-info-circle"

  alertDiv.innerHTML = `
        <i class="fas ${iconClass} me-2"></i>
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
    `

  document.body.appendChild(alertDiv)

  // Автоматически скрываем через 5 секунд
  setTimeout(() => {
    alertDiv.style.animation = "slideOutRight 0.3s ease"
    setTimeout(() => {
      alertDiv.remove()
    }, 300)
  }, 5000)
}

// CSS анимации для уведомлений
const styleSheet = document.createElement("style")
styleSheet.textContent = `
    @keyframes slideInRight {
        from {
            opacity: 0;
            transform: translateX(100px);
        }
        to {
            opacity: 1;
            transform: translateX(0);
        }
    }

    @keyframes slideOutRight {
        from {
            opacity: 1;
            transform: translateX(0);
        }
        to {
            opacity: 0;
            transform: translateX(100px);
        }
    }

    .theme-transitioning * {
        transition: background-color 0.3s ease, 
                    border-color 0.3s ease, 
                    color 0.3s ease !important;
    }
`
document.head.appendChild(styleSheet)

/**
 * Улучшение поиска в select с помощью keyboard navigation
 */
document.addEventListener("keydown", (e) => {
  const activeElement = document.activeElement;
  if (
    activeElement &&
    activeElement.tagName === "SELECT" &&
    e.key.length === 1
  ) {
    const options = Array.from(activeElement.options);
    const currentIndex = activeElement.selectedIndex;
    const char = e.key.toLowerCase();

// Найти следующую опцию, начинающ
