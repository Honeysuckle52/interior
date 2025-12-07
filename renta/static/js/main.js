/**
 * =============================================================================
 * ГЛАВНЫЙ JAVASCRIPT ФАЙЛ
 * Сайт аренды помещений "ИНТЕРЬЕР"
 * =============================================================================
 *
 * СТРУКТУРА:
 * 1. Инициализация при загрузке DOM
 * 2. Управление темой (светлая/тёмная)
 * 3. Избранное (AJAX-запросы)
 * 4. Уведомления (toast)
 * 5. Анимации при прокрутке
 * 6. Вспомогательные функции
 */

/* =============================================================================
   1. ИНИЦИАЛИЗАЦИЯ ПРИ ЗАГРУЗКЕ DOM
   ============================================================================= */
document.addEventListener("DOMContentLoaded", () => {
  // Инициализация всех модулей
  initThemeManager()
  initFavoriteButtons()
  initScrollAnimations()
  initSmoothScroll()
})

/* =============================================================================
   2. УПРАВЛЕНИЕ ТЕМОЙ
   ============================================================================= */

/**
 * Инициализация менеджера темы
 * Отвечает за переключение между светлой и тёмной темой
 * и сохранение выбора пользователя в localStorage
 */
function initThemeManager() {
  const themeToggle = document.getElementById("themeToggle")
  const themeIcon = document.getElementById("themeIcon")
  const html = document.documentElement

  // Получаем сохранённую тему или используем тёмную по умолчанию
  const savedTheme = localStorage.getItem("interior_theme") || "dark"

  // Применяем тему при загрузке
  applyTheme(savedTheme)

  // Обработчик клика на кнопку переключения темы
  if (themeToggle) {
    themeToggle.addEventListener("click", () => {
      const currentTheme = html.getAttribute("data-theme")
      const newTheme = currentTheme === "dark" ? "light" : "dark"

      applyTheme(newTheme)
      localStorage.setItem("interior_theme", newTheme)
    })
  }

  /**
   * Применяет указанную тему к документу
   * @param {string} theme - название темы: 'dark' или 'light'
   */
  function applyTheme(theme) {
    html.setAttribute("data-theme", theme)

    // Обновляем иконку: луна для тёмной темы, солнце для светлой
    if (themeIcon) {
      themeIcon.className = theme === "dark" ? "fas fa-moon" : "fas fa-sun"
    }

    // Обновляем мета-тег цвета для мобильных браузеров
    updateThemeColor(theme)
  }

  /**
   * Обновляет цвет темы в мета-теге для мобильных браузеров
   * @param {string} theme - текущая тема
   */
  function updateThemeColor(theme) {
    let metaThemeColor = document.querySelector('meta[name="theme-color"]')

    if (!metaThemeColor) {
      metaThemeColor = document.createElement("meta")
      metaThemeColor.name = "theme-color"
      document.head.appendChild(metaThemeColor)
    }

    // Устанавливаем цвет фона в зависимости от темы
    metaThemeColor.content = theme === "dark" ? "#0a0a0a" : "#fafafa"
  }
}

/* =============================================================================
   3. ИЗБРАННОЕ (AJAX)
   ============================================================================= */

/**
 * Инициализация всех кнопок избранного на странице
 * Назначает обработчики событий для добавления/удаления из избранного
 */
function initFavoriteButtons() {
  const favoriteButtons = document.querySelectorAll(".space-favorite-btn, .favorite-inline-btn, .favorite-btn")

  favoriteButtons.forEach((btn) => {
    btn.addEventListener("click", handleFavoriteClick)
  })
}

/**
 * Обработчик клика на кнопку избранного
 * Отправляет AJAX-запрос для добавления/удаления помещения из избранного
 * @param {Event} event - событие клика
 */
async function handleFavoriteClick(event) {
  event.preventDefault()
  event.stopPropagation()

  const btn = event.currentTarget
  const spaceId = btn.dataset.spaceId
  const icon = btn.querySelector("i")
  const textEl = btn.querySelector("span, .favorite-text")

  // Получаем CSRF-токен для защиты от межсайтовой подделки запросов
  const csrfToken = getCsrfToken()

  if (!csrfToken) {
    showNotification("Ошибка авторизации. Перезагрузите страницу.", "danger")
    return
  }

  try {
    const response = await fetch(`/spaces/${spaceId}/favorite/`, {
      method: "POST",
      headers: {
        "X-CSRFToken": csrfToken,
        "Content-Type": "application/json",
      },
    })

    if (!response.ok) {
      if (response.status === 403) {
        showNotification("Войдите в систему для добавления в избранное", "warning")
        return
      }
      throw new Error("Ошибка сервера")
    }

    const data = await response.json()
    const isFavorite = data.is_favorite || data.status === "added"

    // Обновляем внешний вид кнопки
    updateFavoriteButton(btn, icon, textEl, isFavorite)

    // Показываем уведомление об успехе
    const message = data.message || (isFavorite ? "Добавлено в избранное" : "Удалено из избранного")
    showNotification(message, "success")

    // Если на странице избранного - анимируем удаление карточки
    if (!isFavorite && btn.closest(".col-lg-4, .col-md-6")) {
      const card = btn.closest(".col-lg-4, .col-md-6")
      // Проверяем, что мы на странице избранного
      if (window.location.pathname.includes("favorites")) {
        animateCardRemoval(card)
      }
    }
  } catch (error) {
    console.error("Ошибка при изменении избранного:", error)
    showNotification("Произошла ошибка. Попробуйте ещё раз.", "danger")
  }
}

/**
 * Обновляет визуальное состояние кнопки избранного
 * @param {Element} btn - кнопка избранного
 * @param {Element} icon - иконка сердца
 * @param {Element} textEl - текстовый элемент (если есть)
 * @param {boolean} isFavorite - добавлено ли в избранное
 */
function updateFavoriteButton(btn, icon, textEl, isFavorite) {
  btn.classList.toggle("active", isFavorite)

  if (icon) {
    // Меняем иконку: закрашенное сердце для избранного, контурное для обычного
    icon.classList.remove("fas", "far")
    icon.classList.add(isFavorite ? "fas" : "far")
  }

  if (textEl) {
    textEl.textContent = isFavorite ? "В избранном" : "В избранное"
  }
}

/**
 * Анимирует удаление карточки с плавным исчезновением
 * @param {Element} card - элемент карточки для удаления
 */
function animateCardRemoval(card) {
  card.style.transition = "opacity 0.3s, transform 0.3s"
  card.style.opacity = "0"
  card.style.transform = "scale(0.95)"

  setTimeout(() => {
    card.remove()

    // Если карточек не осталось - перезагружаем страницу
    if (document.querySelectorAll(".space-card").length === 0) {
      location.reload()
    }
  }, 300)
}

/* =============================================================================
   4. УВЕДОМЛЕНИЯ (TOAST)
   ============================================================================= */

/**
 * Показывает всплывающее уведомление
 * @param {string} message - текст сообщения
 * @param {string} type - тип: 'success', 'danger', 'warning', 'info'
 */
function showNotification(message, type = "success") {
  // Удаляем предыдущее уведомление, если есть
  const existingToast = document.querySelector(".notification-toast")
  if (existingToast) {
    existingToast.remove()
  }

  // Создаём новое уведомление
  const toast = document.createElement("div")
  toast.className = `notification-toast alert alert-${type}`
  toast.innerHTML = `
    <div style="display: flex; align-items: center; gap: 0.625rem;">
      <i class="fas ${getNotificationIcon(type)}"></i>
      <span>${message}</span>
    </div>
  `

  document.body.appendChild(toast)

  // Автоматическое скрытие через 3 секунды
  setTimeout(() => {
    toast.style.animation = "slideOut 0.3s ease forwards"
    setTimeout(() => toast.remove(), 300)
  }, 3000)
}

/**
 * Возвращает класс иконки для типа уведомления
 * @param {string} type - тип уведомления
 * @returns {string} - класс иконки FontAwesome
 */
function getNotificationIcon(type) {
  const icons = {
    success: "fa-check-circle",
    danger: "fa-times-circle",
    warning: "fa-exclamation-triangle",
    info: "fa-info-circle",
  }
  return icons[type] || icons.info
}

/* =============================================================================
   5. АНИМАЦИИ ПРИ ПРОКРУТКЕ
   ============================================================================= */

/**
 * Инициализация анимаций появления элементов при прокрутке
 * Использует Intersection Observer для отслеживания видимости
 */
function initScrollAnimations() {
  // Настройки наблюдателя
  const observerOptions = {
    threshold: 0.1,
    rootMargin: "0px 0px -40px 0px",
  }

  const observer = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        entry.target.classList.add("animate-fade-in")
        observer.unobserve(entry.target)
      }
    })
  }, observerOptions)

  // Наблюдаем за карточками и другими анимируемыми элементами
  const animatedElements = document.querySelectorAll(".space-card, .dashboard-card, .glass-card")
  animatedElements.forEach((el) => observer.observe(el))
}

/**
 * Инициализация плавной прокрутки к якорям
 */
function initSmoothScroll() {
  document.querySelectorAll('a[href^="#"]').forEach((anchor) => {
    anchor.addEventListener("click", function (e) {
      const targetId = this.getAttribute("href")

      if (targetId === "#") return

      const target = document.querySelector(targetId)

      if (target) {
        e.preventDefault()
        target.scrollIntoView({
          behavior: "smooth",
          block: "start",
        })
      }
    })
  })
}

/* =============================================================================
   6. ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
   ============================================================================= */

/**
 * Получает CSRF-токен из cookies или скрытого поля формы
 * @returns {string|null} - CSRF-токен или null
 */
function getCsrfToken() {
  // Сначала ищем в cookies
  const cookieToken = getCookie("csrftoken")
  if (cookieToken) return cookieToken

  // Затем в скрытом поле формы
  const tokenInput = document.querySelector("[name=csrfmiddlewaretoken]")
  return tokenInput ? tokenInput.value : null
}

/**
 * Получает значение cookie по имени
 * @param {string} name - имя cookie
 * @returns {string|null} - значение или null
 */
function getCookie(name) {
  if (!document.cookie) return null

  const cookies = document.cookie.split(";")

  for (let cookie of cookies) {
    cookie = cookie.trim()

    if (cookie.startsWith(name + "=")) {
      return decodeURIComponent(cookie.substring(name.length + 1))
    }
  }

  return null
}

/**
 * Форматирует число как цену в рублях
 * @param {number} price - сумма
 * @returns {string} - отформатированная строка
 */
function formatPrice(price) {
  return new Intl.NumberFormat("ru-RU", {
    style: "currency",
    currency: "RUB",
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(price)
}

/**
 * Функция debounce для оптимизации частых вызовов
 * @param {Function} func - функция для оптимизации
 * @param {number} wait - задержка в миллисекундах
 * @returns {Function} - оптимизированная функция
 */
function debounce(func, wait) {
  let timeout

  return function executedFunction(...args) {
    const later = () => {
      clearTimeout(timeout)
      func(...args)
    }

    clearTimeout(timeout)
    timeout = setTimeout(later, wait)
  }
}

/* =============================================================================
   ЭКСПОРТ ФУНКЦИЙ ДЛЯ ИСПОЛЬЗОВАНИЯ В INLINE-СКРИПТАХ
   ============================================================================= */
window.InteriorApp = {
  showNotification,
  formatPrice,
  getCsrfToken,
  debounce,
}
