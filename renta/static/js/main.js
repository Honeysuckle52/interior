/**
 * =============================================================================
 * ГЛАВНЫЙ JAVASCRIPT ФАЙЛ
 * Сайт аренды помещений "ИНТЕРЬЕР"
 * =============================================================================
 */

/* =============================================================================
   1. ИНИЦИАЛИЗАЦИЯ ПРИ ЗАГРУЗКЕ DOM
   ============================================================================= */
document.addEventListener("DOMContentLoaded", () => {
  initThemeManager()
  initFavoriteButtons()
  initScrollAnimations()
  initSmoothScroll()
  initButtonAnimations()
  initFormEnhancements()
  initReviewForm()
})

/* =============================================================================
   2. УПРАВЛЕНИЕ ТЕМОЙ - ЗАМЕДЛЕННЫЕ АНИМАЦИИ
   ============================================================================= */
function initThemeManager() {
  const themeToggle = document.getElementById("themeToggle")
  const themeIcon = document.getElementById("themeIcon")
  const html = document.documentElement

  const savedTheme = localStorage.getItem("interior_theme")
  const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches
  const initialTheme = savedTheme || (prefersDark ? "dark" : "light")

  applyTheme(initialTheme, false)

  if (themeToggle) {
    themeToggle.addEventListener("click", () => {
      const currentTheme = html.getAttribute("data-theme")
      const newTheme = currentTheme === "dark" ? "light" : "dark"

      themeToggle.style.transform = "rotate(360deg) scale(0.8)"
      themeToggle.style.transition = "transform 0.4s cubic-bezier(0.68, -0.55, 0.265, 1.55)"

      setTimeout(() => {
        applyTheme(newTheme, true)
        localStorage.setItem("interior_theme", newTheme)
        themeToggle.style.transform = ""
      }, 250)
    })
  }

  window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", (e) => {
    if (!localStorage.getItem("interior_theme")) {
      applyTheme(e.matches ? "dark" : "light", true)
    }
  })

  function applyTheme(theme, animate = true) {
    if (animate) {
      html.style.transition = "background-color 0.5s ease, color 0.5s ease"
    }

    html.setAttribute("data-theme", theme)

    if (themeIcon) {
      if (animate) {
        themeIcon.style.transform = "scale(0)"
        setTimeout(() => {
          themeIcon.className = theme === "dark" ? "fas fa-moon" : "fas fa-sun"
          themeIcon.style.transform = "scale(1)"
        }, 250)
      } else {
        themeIcon.className = theme === "dark" ? "fas fa-moon" : "fas fa-sun"
      }
    }

    updateThemeColor(theme)
  }

  function updateThemeColor(theme) {
    let metaThemeColor = document.querySelector('meta[name="theme-color"]')

    if (!metaThemeColor) {
      metaThemeColor = document.createElement("meta")
      metaThemeColor.name = "theme-color"
      document.head.appendChild(metaThemeColor)
    }

    metaThemeColor.content = theme === "dark" ? "#0a0a0a" : "#fafafa"
  }
}

/* =============================================================================
   3. ФОРМА ОТЗЫВОВ - ИСПРАВЛЕНО
   ============================================================================= */
function initReviewForm() {
  const starRating = document.getElementById("starRating")
  const ratingValue = document.getElementById("ratingValue")
  const reviewForm = document.getElementById("reviewForm")

  if (starRating && ratingValue) {
    const starInputs = starRating.querySelectorAll('input[type="radio"]')
    const starLabels = starRating.querySelectorAll("label")

    starInputs.forEach((input) => {
      input.addEventListener("change", function () {
        ratingValue.value = this.value
      })
    })

    starLabels.forEach((label) => {
      label.addEventListener("click", function () {
        const forAttr = this.getAttribute("for")
        const input = document.getElementById(forAttr)
        if (input) {
          input.checked = true
          ratingValue.value = input.value
        }
      })
    })
  }

  if (reviewForm) {
    reviewForm.addEventListener("submit", (e) => {
      if (!ratingValue || !ratingValue.value) {
        e.preventDefault()
        showNotification("Пожалуйста, выберите оценку (звёзды)", "warning")
        return false
      }
    })
  }
}

/* =============================================================================
   4. АНИМАЦИИ КНОПОК
   ============================================================================= */
function initButtonAnimations() {
  document.querySelectorAll(".btn").forEach((btn) => {
    btn.addEventListener("click", function (e) {
      const rect = this.getBoundingClientRect()
      const x = e.clientX - rect.left
      const y = e.clientY - rect.top

      const ripple = document.createElement("span")
      ripple.style.cssText = `
        position: absolute;
        background: rgba(255, 255, 255, 0.3);
        border-radius: 50%;
        transform: scale(0);
        animation: ripple 0.6s linear;
        pointer-events: none;
        left: ${x}px;
        top: ${y}px;
        width: 100px;
        height: 100px;
        margin-left: -50px;
        margin-top: -50px;
      `

      this.style.position = "relative"
      this.style.overflow = "hidden"
      this.appendChild(ripple)

      setTimeout(() => ripple.remove(), 600)
    })
  })

  if (!document.getElementById("ripple-styles")) {
    const style = document.createElement("style")
    style.id = "ripple-styles"
    style.textContent = `
      @keyframes ripple {
        to {
          transform: scale(4);
          opacity: 0;
        }
      }
    `
    document.head.appendChild(style)
  }
}

/* =============================================================================
   5. УЛУЧШЕНИЯ ФОРМ
   ============================================================================= */
function initFormEnhancements() {
  document.querySelectorAll(".form-control, .form-select").forEach((input) => {
    input.addEventListener("focus", function () {
      this.parentElement?.classList.add("input-focused")
    })

    input.addEventListener("blur", function () {
      this.parentElement?.classList.remove("input-focused")
    })
  })

  document.querySelectorAll("textarea").forEach((textarea) => {
    textarea.addEventListener("input", function () {
      this.style.height = "auto"
      this.style.height = Math.min(this.scrollHeight, 300) + "px"
    })
  })
}

/* =============================================================================
   6. ИЗБРАННОЕ (AJAX) - Полностью переписана логика для исправления бага
   ============================================================================= */
function initFavoriteButtons() {
  // Удаляем старый обработчик если есть
  document.removeEventListener("click", handleFavoriteClickDelegate)
  // Добавляем новый глобальный обработчик
  document.addEventListener("click", handleFavoriteClickDelegate)
}

function handleFavoriteClickDelegate(event) {
  // Находим кнопку избранного среди целевых элементов клика
  const btn = event.target.closest(".space-favorite-btn")
  if (!btn) return

  event.preventDefault()
  event.stopPropagation()

  handleFavoriteClick(btn)
}

async function handleFavoriteClick(btn) {
  const spaceId = btn.dataset.spaceId

  if (!spaceId) {
    console.error("Не найден data-space-id на кнопке избранного")
    return
  }

  const icon = btn.querySelector("i")
  const csrfToken = getCsrfToken()

  if (!csrfToken) {
    showNotification("Ошибка авторизации. Перезагрузите страницу.", "danger")
    return
  }

  // Блокируем кнопку на время запроса
  btn.disabled = true

  // Анимация нажатия
  btn.style.transform = "scale(0.85)"
  btn.style.transition = "transform 0.15s cubic-bezier(0.68, -0.55, 0.265, 1.55)"

  try {
    const response = await fetch(`/spaces/${spaceId}/favorite/`, {
      method: "POST",
      headers: {
        "X-CSRFToken": csrfToken,
        "Content-Type": "application/json",
        "X-Requested-With": "XMLHttpRequest",
      },
      credentials: "same-origin",
    })

    if (!response.ok) {
      if (response.status === 403) {
        showNotification("Войдите в систему для добавления в избранное", "warning")
        btn.style.transform = "scale(1)"
        btn.disabled = false
        return
      }
      throw new Error(`HTTP error! status: ${response.status}`)
    }

    const data = await response.json()
    const isFavorite = data.status === "added"

    // Обновляем состояние кнопки
    btn.classList.toggle("active", isFavorite)

    if (icon) {
      icon.classList.remove("fas", "far")
      icon.classList.add(isFavorite ? "fas" : "far")

      if (isFavorite) {
        icon.style.animation = "heartPulse 0.6s ease"
        setTimeout(() => {
          icon.style.animation = ""
        }, 600)
      }
    }

    btn.title = isFavorite ? "Удалить из избранного" : "Добавить в избранное"

    // Анимация после успешного запроса
    setTimeout(() => {
      btn.style.transform = isFavorite ? "scale(1.2)" : "scale(1)"
      setTimeout(() => {
        btn.style.transform = "scale(1)"
      }, 150)
    }, 100)

    const message = data.message || (isFavorite ? "Добавлено в избранное" : "Удалено из избранного")
    showNotification(message, "success")

    // Удаление карточки на странице избранного
    if (!isFavorite && window.location.pathname.includes("favorites")) {
      const card = btn.closest(".col-lg-4, .col-md-6")
      if (card) {
        card.style.transition = "all 0.4s cubic-bezier(0.4, 0, 0.2, 1)"
        card.style.opacity = "0"
        card.style.transform = "scale(0.8) translateY(20px)"

        setTimeout(() => {
          card.remove()
          if (document.querySelectorAll(".space-card").length === 0) {
            location.reload()
          }
        }, 400)
      }
    }
  } catch (error) {
    console.error("Ошибка при изменении избранного:", error)
    showNotification("Произошла ошибка. Попробуйте ещё раз.", "danger")
    btn.style.transform = "scale(1)"
  } finally {
    btn.disabled = false
  }
}

/* =============================================================================
   7. УВЕДОМЛЕНИЯ (TOAST)
   ============================================================================= */
function showNotification(message, type = "success") {
  const existingToast = document.querySelector(".notification-toast")
  if (existingToast) {
    existingToast.style.animation = "slideOut 0.3s ease forwards"
    setTimeout(() => existingToast.remove(), 300)
  }

  const toast = document.createElement("div")
  toast.className = `notification-toast alert alert-${type}`
  toast.innerHTML = `
    <div style="display: flex; align-items: center; gap: 0.75rem;">
      <i class="fas ${getNotificationIcon(type)}" style="font-size: 1.1rem;"></i>
      <span style="flex: 1;">${message}</span>
      <button type="button" style="background: none; border: none; cursor: pointer; opacity: 0.7; padding: 0; color: inherit;" onclick="this.parentElement.parentElement.remove()">
        <i class="fas fa-times"></i>
      </button>
    </div>
  `

  document.body.appendChild(toast)

  setTimeout(() => {
    if (toast.parentElement) {
      toast.style.animation = "slideOut 0.3s ease forwards"
      setTimeout(() => toast.remove(), 300)
    }
  }, 4000)
}

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
   8. АНИМАЦИИ ПРИ ПРОКРУТКЕ
   ============================================================================= */
function initScrollAnimations() {
  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
    return
  }

  const observerOptions = {
    threshold: 0.1,
    rootMargin: "0px 0px -50px 0px",
  }

  const observer = new IntersectionObserver((entries) => {
    entries.forEach((entry, index) => {
      if (entry.isIntersecting) {
        setTimeout(() => {
          entry.target.classList.add("animate-fade-in")
        }, index * 50)
        observer.unobserve(entry.target)
      }
    })
  }, observerOptions)

  const animatedElements = document.querySelectorAll(".space-card, .dashboard-card, .glass-card, .detail-card")
  animatedElements.forEach((el) => {
    el.style.opacity = "0"
    observer.observe(el)
  })
}

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
   9. ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
   ============================================================================= */
function getCsrfToken() {
  // Сначала пробуем из cookie
  const cookieToken = getCookie("csrftoken")
  if (cookieToken) return cookieToken

  // Затем из скрытого поля формы
  const tokenInput = document.querySelector("[name=csrfmiddlewaretoken]")
  if (tokenInput) return tokenInput.value

  // Из meta тега
  const metaToken = document.querySelector('meta[name="csrf-token"]')
  if (metaToken) return metaToken.getAttribute("content")

  return null
}

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

function formatPrice(price) {
  return new Intl.NumberFormat("ru-RU", {
    style: "currency",
    currency: "RUB",
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(price)
}

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
   ЭКСПОРТ ФУНКЦИЙ
   ============================================================================= */
window.InteriorApp = {
  showNotification,
  formatPrice,
  getCsrfToken,
  debounce,
  initFavoriteButtons,
  initReviewForm,
}
