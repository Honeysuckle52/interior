/**
 * ГЛАВНЫЙ JAVASCRIPT ФАЙЛ ДЛЯ САЙТА АРЕНДЫ ПОМЕЩЕНИЙ
 */

document.addEventListener("DOMContentLoaded", () => {
  // Убираем класс loading после загрузки
  document.body.classList.remove("loading")

  // Инициализация компонентов
  initThemeToggle()
  initFavoriteButtons()
  initSmoothScroll()
  initAnimations()
})

/**
 * Переключение темы (светлая/темная)
 */
function initThemeToggle() {
  const themeToggle = document.getElementById("themeToggle")
  const themeIcon = document.getElementById("themeIcon")
  const html = document.documentElement

  // Проверяем сохраненную тему
  const savedTheme = localStorage.getItem("theme") || "dark"
  html.setAttribute("data-theme", savedTheme)
  updateThemeIcon(savedTheme)

  if (themeToggle) {
    themeToggle.addEventListener("click", () => {
      const currentTheme = html.getAttribute("data-theme")
      const newTheme = currentTheme === "dark" ? "light" : "dark"

      html.setAttribute("data-theme", newTheme)
      localStorage.setItem("theme", newTheme)
      updateThemeIcon(newTheme)
    })
  }

  function updateThemeIcon(theme) {
    if (themeIcon) {
      themeIcon.className = theme === "dark" ? "fas fa-moon" : "fas fa-sun"
    }
  }
}

/**
 * Обработка кнопок избранного
 */
function initFavoriteButtons() {
  document.querySelectorAll(".favorite-btn").forEach((btn) => {
    btn.addEventListener("click", async function (e) {
      e.preventDefault()
      e.stopPropagation()

      const spaceId = this.dataset.spaceId
      const icon = this.querySelector("i")

      try {
        const response = await fetch(`/spaces/${spaceId}/favorite/`, {
          method: "POST",
          headers: {
            "X-CSRFToken": getCookie("csrftoken"),
            "Content-Type": "application/json",
          },
        })

        const data = await response.json()

        if (data.status === "added") {
          this.classList.add("active")
          icon.classList.remove("far")
          icon.classList.add("fas")
        } else {
          this.classList.remove("active")
          icon.classList.remove("fas")
          icon.classList.add("far")
        }

        // Показываем уведомление
        showNotification(data.message)
      } catch (error) {
        console.error("Ошибка:", error)
        showNotification("Войдите в систему", "warning")
      }
    })
  })
}

/**
 * Плавная прокрутка
 */
function initSmoothScroll() {
  document.querySelectorAll('a[href^="#"]').forEach((anchor) => {
    anchor.addEventListener("click", function (e) {
      e.preventDefault()
      const target = document.querySelector(this.getAttribute("href"))
      if (target) {
        target.scrollIntoView({
          behavior: "smooth",
          block: "start",
        })
      }
    })
  })
}

/**
 * Анимации при прокрутке
 */
function initAnimations() {
  const observerOptions = {
    threshold: 0.1,
    rootMargin: "0px 0px -50px 0px",
  }

  const observer = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        entry.target.classList.add("animate-fade-in")
        observer.unobserve(entry.target)
      }
    })
  }, observerOptions)

  document.querySelectorAll(".space-card, .dashboard-card").forEach((el) => {
    observer.observe(el)
  })
}

/**
 * Показать уведомление
 */
function showNotification(message, type = "success") {
  // Удаляем старое уведомление
  const oldNotification = document.querySelector(".notification-toast")
  if (oldNotification) {
    oldNotification.remove()
  }

  // Создаем новое
  const notification = document.createElement("div")
  notification.className = `notification-toast alert alert-${type}`
  notification.style.cssText = `
        position: fixed;
        bottom: 20px;
        right: 20px;
        z-index: 9999;
        min-width: 250px;
        animation: slideIn 0.3s ease;
    `
  notification.textContent = message

  document.body.appendChild(notification)

  // Удаляем через 3 секунды
  setTimeout(() => {
    notification.style.animation = "slideOut 0.3s ease"
    setTimeout(() => notification.remove(), 300)
  }, 3000)
}

/**
 * Получение CSRF токена из cookies
 */
function getCookie(name) {
  let cookieValue = null
  if (document.cookie && document.cookie !== "") {
    const cookies = document.cookie.split(";")
    for (let i = 0; i < cookies.length; i++) {
      const cookie = cookies[i].trim()
      if (cookie.substring(0, name.length + 1) === name + "=") {
        cookieValue = decodeURIComponent(cookie.substring(name.length + 1))
        break
      }
    }
  }
  return cookieValue
}

/**
 * Форматирование цены
 */
function formatPrice(price) {
  return new Intl.NumberFormat("ru-RU", {
    style: "currency",
    currency: "RUB",
    minimumFractionDigits: 0,
  }).format(price)
}

// CSS анимации для уведомлений
const style = document.createElement("style")
style.textContent = `
    @keyframes slideIn {
        from { transform: translateX(100%); opacity: 0; }
        to { transform: translateX(0); opacity: 1; }
    }
    @keyframes slideOut {
        from { transform: translateX(0); opacity: 1; }
        to { transform: translateX(100%); opacity: 0; }
    }
`
document.head.appendChild(style)
