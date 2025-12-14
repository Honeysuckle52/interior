/*** Кастомный JavaScript для Django Jazzmin Admin Panel
 * ООО "ИНТЕРЬЕР" - Поддержка переключения светлой/тёмной темы
 * Версия 7.0 - Улучшенная стабильность, исправление sidebar, оптимизация производительности
 */

;(() => {
  // Конфигурация
  const CONFIG = {
    STORAGE_KEY: "admin-theme",
    THEME_TRANSITION_DURATION: 400,
    ANIMATION_DELAY: 50,
    ANIMATION_STEP: 30,
  }

  // Инициализация после загрузки DOM
  document.addEventListener("DOMContentLoaded", init)

  /**
   * Главная функция инициализации
   */
  function init() {
    applySavedTheme()
    createThemeToggle()
    addLoadAnimations()
    fixSidebarBehavior()
    enhanceTableInteractions()
  }

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

    const isDark = !document.body.classList.contains("light-mode")
    toggle.innerHTML = isDark ? '<i class="fas fa-moon"></i>' : '<i class="fas fa-sun"></i>'

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

    // Добавляем класс для плавной анимации
    body.classList.add("theme-transitioning")

    if (isLight) {
      // Переключаем на тёмную
      body.classList.remove("light-mode")
      body.removeAttribute("data-theme")
      if (toggle) toggle.innerHTML = '<i class="fas fa-moon"></i>'
      localStorage.setItem(CONFIG.STORAGE_KEY, "dark")
      updateBootstrapTheme("dark")
    } else {
      // Переключаем на светлую
      body.classList.add("light-mode")
      body.setAttribute("data-theme", "light")
      if (toggle) toggle.innerHTML = '<i class="fas fa-sun"></i>'
      localStorage.setItem(CONFIG.STORAGE_KEY, "light")
      updateBootstrapTheme("light")
    }

    // Убираем класс анимации после завершения перехода
    setTimeout(() => {
      body.classList.remove("theme-transitioning")
    }, CONFIG.THEME_TRANSITION_DURATION)
  }

  /**
   * Применяет сохранённую тему при загрузке
   */
  function applySavedTheme() {
    const savedTheme = localStorage.getItem(CONFIG.STORAGE_KEY) || "dark"
    const body = document.body
    const toggle = document.getElementById("theme-toggle")

    if (savedTheme === "light") {
      body.classList.add("light-mode")
      body.setAttribute("data-theme", "light")
      if (toggle) toggle.innerHTML = '<i class="fas fa-sun"></i>'
      updateBootstrapTheme("light")
    } else {
      body.classList.remove("light-mode")
      body.removeAttribute("data-theme")
      if (toggle) toggle.innerHTML = '<i class="fas fa-moon"></i>'
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
        sidebar.classList.remove("sidebar-dark-warning", "sidebar-dark-primary")
        sidebar.classList.add("sidebar-light-warning")
      }
    } else {
      // Тёмная тема
      if (navbar) {
        navbar.classList.remove("navbar-light")
        navbar.classList.add("navbar-dark")
      }
      if (sidebar) {
        sidebar.classList.remove("sidebar-light-warning", "sidebar-light-primary")
        sidebar.classList.add("sidebar-dark-warning")
      }
    }
  }

  /**
   * Исправляет поведение sidebar
   */
  function fixSidebarBehavior() {
    const sidebar = document.querySelector(".main-sidebar")
    const contentWrapper = document.querySelector(".content-wrapper")
    const navbar = document.querySelector(".main-header.navbar")
    const footer = document.querySelector(".main-footer")

    if (!sidebar) return

    // Обработчик для кнопки сворачивания sidebar
    const sidebarToggle = document.querySelector('[data-widget="pushmenu"]')
    if (sidebarToggle) {
      sidebarToggle.addEventListener("click", () => {
        // Даем время на применение классов AdminLTE
        setTimeout(() => {
          const isCollapsed = document.body.classList.contains("sidebar-collapse")

          // Обновляем CSS переменную для плавной анимации
          document.documentElement.style.setProperty("--sidebar-width", isCollapsed ? "4.6rem" : "250px")
        }, 10)
      })
    }

    // Фикс для hover на свернутом sidebar
    sidebar.addEventListener("mouseenter", () => {
      if (document.body.classList.contains("sidebar-collapse")) {
        sidebar.classList.add("sidebar-focused")
      }
    })

    sidebar.addEventListener("mouseleave", () => {
      sidebar.classList.remove("sidebar-focused")
    })
  }

  /**
   * Улучшает взаимодействие с таблицами
   */
  function enhanceTableInteractions() {
    const tables = document.querySelectorAll(".table")

    tables.forEach((table) => {
      // Добавляем плавное подсвечивание строк
      const rows = table.querySelectorAll("tbody tr")
      rows.forEach((row) => {
        row.addEventListener("mouseenter", () => {
          row.style.transition = "background-color 0.2s ease"
        })
      })
    })

    // Улучшаем чекбоксы "выбрать все"
    const selectAllCheckbox = document.querySelector("#action-toggle")
    if (selectAllCheckbox) {
      selectAllCheckbox.addEventListener("change", function () {
        const checkboxes = document.querySelectorAll(".action-select")
        checkboxes.forEach((cb) => {
          cb.checked = this.checked
          // Визуальная обратная связь
          const row = cb.closest("tr")
          if (row) {
            row.style.backgroundColor = this.checked ? "rgba(212, 175, 55, 0.1)" : ""
          }
        })
      })
    }
  }

  /**
   * Добавляет анимации при загрузке страницы
   */
  function addLoadAnimations() {
    // Проверяем предпочтения пользователя по анимациям
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      return
    }

    const animatableElements = document.querySelectorAll(
      ".card, .info-box, .small-box, .stat-card, .chart-card, .data-card, .report-section, .backup-section",
    )

    animatableElements.forEach((element, index) => {
      element.style.opacity = "0"
      element.style.transform = "translateY(20px)"

      setTimeout(
        () => {
          element.style.transition = "opacity 0.4s ease, transform 0.4s ease"
          element.style.opacity = "1"
          element.style.transform = "translateY(0)"
        },
        CONFIG.ANIMATION_DELAY + index * CONFIG.ANIMATION_STEP,
      )
    })
  }

  // Экспортируем функции для внешнего использования (если нужно)
  window.AdminTheme = {
    toggle: toggleTheme,
    apply: applySavedTheme,
    isDark: () => !document.body.classList.contains("light-mode"),
  }
})()
