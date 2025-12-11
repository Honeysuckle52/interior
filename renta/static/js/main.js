/**
 * =============================================================================
 * ГЛАВНЫЙ JAVASCRIPT ФАЙЛ
 * Сайт аренды помещений "ИНТЕРЬЕР"
 * =============================================================================
 * Полностью переработанная версия с улучшениями:
 * - Чистая архитектура
 * - Поддержка темной/светлой темы
 * - Оптимизированные анимации
 * - Корректная обработка AJAX
 * - Поддержка prefers-reduced-motion
 * - Улучшенные уведомления и ripple-эффекты
 * =============================================================================
 */

// =============================
// ВСПОМОГАТЕЛЬНЫЕ УТИЛИТЫ
// =============================

function getCsrfToken() {
  const cookie = document.cookie
    .split("; ")
    .find((row) => row.startsWith("csrftoken="))
    ?.split("=")[1]
  if (cookie) return cookie

  const input = document.querySelector('input[name="csrfmiddlewaretoken"]')
  if (input) return input.value

  const meta = document.querySelector('meta[name="csrf-token"]')
  if (meta) return meta.content

  console.warn("CSRF token not found")
  return null
}

function showNotification(message, type = "success") {
  const oldToast = document.querySelector(".notification-toast")
  if (oldToast) {
    oldToast.style.animation = "slideOut 0.3s ease forwards"
    setTimeout(() => oldToast.remove(), 300)
  }

  const icons = {
    success: "fa-check-circle",
    danger: "fa-times-circle",
    warning: "fa-exclamation-triangle",
    info: "fa-info-circle",
  }

  const toast = document.createElement("div")
  toast.className = `notification-toast alert alert-${type}`
  toast.innerHTML = `
    <div style="display: flex; align-items: center; gap: 0.75rem;">
      <i class="fas ${icons[type] || icons.info}" style="font-size: 1.1rem;"></i>
      <span>${message}</span>
      <button type="button" style="background: none; border: none; cursor: pointer; opacity: 0.7; padding: 0; color: inherit;">
        <i class="fas fa-times"></i>
      </button>
    </div>
  `

  document.body.appendChild(toast)

  toast.querySelector("button").addEventListener("click", () => {
    toast.style.animation = "slideOut 0.3s ease forwards"
    setTimeout(() => toast.remove(), 300)
  })

  setTimeout(() => {
    if (toast.parentElement) {
      toast.style.animation = "slideOut 0.3s ease forwards"
      setTimeout(() => toast.remove(), 300)
    }
  }, 4000)
}

function formatPrice(price) {
  return new Intl.NumberFormat("ru-RU", {
    style: "currency",
    currency: "RUB",
    minimumFractionDigits: 0,
  }).format(price)
}

// =============================
// ИНИЦИАЛИЗАЦИЯ
// =============================

document.addEventListener("DOMContentLoaded", () => {
  initThemeManager()
  initFavoriteButtons()
  initScrollAnimations()
  initSmoothScroll()
  initButtonAnimations()
  initFormEnhancements()
  initReviewForm()
  initConfirmForms()
})

// =============================
// НОВАЯ ФУНКЦИЯ: ПОДТВЕРЖДЕНИЕ ФОРМ
// =============================

function initConfirmForms() {
  document.querySelectorAll(".confirm-form").forEach((form) => {
    form.addEventListener("submit", (e) => {
      const message = form.dataset.message || "Вы уверены?"
      if (!confirm(message)) {
        e.preventDefault()
      }
    })
  })
}

// =============================
// УПРАВЛЕНИЕ ТЕМОЙ (ИСПРАВЛЕНО)
// =============================

function initThemeManager() {
  const html = document.documentElement
  const themeToggle = document.getElementById("themeToggle")
  const themeIcon = document.getElementById("themeIcon")

  if (!themeToggle) return

  // Определяем начальную тему
  const saved = localStorage.getItem("interior_theme")
  const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches
  const initialTheme = saved || (prefersDark ? "dark" : "light")

  // Применяем тему без анимации при загрузке
  applyTheme(initialTheme, false)

  // Обработчик переключения темы
  themeToggle.addEventListener("click", () => {
    const current = html.getAttribute("data-theme")
    const newTheme = current === "dark" ? "light" : "dark"

    // Анимация кнопки
    themeToggle.style.transform = "scale(0.9) rotate(15deg)"
    setTimeout(() => (themeToggle.style.transform = ""), 150)

    applyTheme(newTheme, true)
    localStorage.setItem("interior_theme", newTheme)
  })

  // Обновление при изменении системных настроек (если нет сохранённой темы)
  window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", (e) => {
    if (!localStorage.getItem("interior_theme")) {
      applyTheme(e.matches ? "dark" : "light", true)
    }
  })

  function applyTheme(theme, animate = true) {
    // Правильное управление анимацией: устанавливаем transition до изменения атрибута
    if (animate) {
      html.style.setProperty("transition", "background-color var(--transition-theme), color var(--transition-theme)")
    } else {
      // Если анимация отключена, удаляем transition
      html.style.removeProperty("transition")
    }

    // Меняем тему
    html.setAttribute("data-theme", theme)

    // Обновляем иконку
    if (themeIcon) {
      themeIcon.className = theme === "dark" ? "fas fa-moon" : "fas fa-sun"
    }

    // Обновляем meta для PWA/мобильных
    let meta = document.querySelector('meta[name="theme-color"]')
    if (!meta) {
      meta = document.createElement("meta")
      meta.name = "theme-color"
      document.head.appendChild(meta)
    }
    meta.content = theme === "dark" ? "#0a0a0a" : "#fafafa"

    // Удаляем transition после завершения анимации, чтобы не мешало другим анимациям
    if (animate) {
      setTimeout(() => {
        // Проверяем, не изменилась ли тема во время ожидания
        if (html.getAttribute("data-theme") === theme) {
          html.style.removeProperty("transition")
        }
      }, 400) // 400ms - время анимации темы
    }
  }
}

// =============================
// ИЗБРАННОЕ
// =============================

function initFavoriteButtons() {
  document.addEventListener("click", async (e) => {
    // Поддержка двух классов кнопок: space-favorite-btn и favorite-inline-btn
    const btn = e.target.closest(".space-favorite-btn, .favorite-inline-btn")
    if (!btn) return

    e.preventDefault()
    e.stopPropagation()

    const spaceId = btn.dataset.spaceId
    if (!spaceId) {
      console.error("Missing data-space-id on favorite button")
      return
    }

    const csrf = getCsrfToken()
    if (!csrf) {
      showNotification("Ошибка авторизации. Обновите страницу.", "danger")
      return
    }

    const icon = btn.querySelector("i")
    const textSpan = btn.querySelector("span") // Для inline кнопок с текстом
    const wasActive = btn.classList.contains("active")
    const originalTransform = btn.style.transform

    // Визуальная блокировка
    btn.disabled = true
    btn.style.transform = "scale(0.85)"

    try {
      const res = await fetch(`/spaces/${spaceId}/favorite/`, {
        method: "POST",
        headers: {
          "X-CSRFToken": csrf,
          "Content-Type": "application/json",
          "X-Requested-With": "XMLHttpRequest",
        },
      })

      if (!res.ok) {
        if (res.status === 403) {
          showNotification("Войдите, чтобы добавить в избранное", "warning")
          return
        }
        throw new Error(`HTTP ${res.status}`)
      }

      const data = await res.json()
      const isActive = data.status === "added"

      // Обновляем внешний вид
      btn.classList.toggle("active", isActive)
      if (icon) {
        icon.className = isActive ? "fas fa-heart" : "far fa-heart"
        if (isActive) {
          icon.style.animation = "heartPulse 0.6s"
          setTimeout(() => (icon.style.animation = ""), 600)
        }
      }

      if (textSpan) {
        textSpan.textContent = isActive ? "В избранном" : "В избранное"
      }

      btn.title = isActive ? "Удалить из избранного" : "Добавить в избранное"

      // Уведомление
      showNotification(isActive ? "Добавлено в избранное" : "Удалено из избранного", "success")

      document.querySelectorAll(`[data-space-id="${spaceId}"]`).forEach((otherBtn) => {
        if (
          otherBtn !== btn &&
          (otherBtn.classList.contains("space-favorite-btn") || otherBtn.classList.contains("favorite-inline-btn"))
        ) {
          otherBtn.classList.toggle("active", isActive)
          const otherIcon = otherBtn.querySelector("i")
          const otherText = otherBtn.querySelector("span")
          if (otherIcon) {
            otherIcon.className = isActive ? "fas fa-heart" : "far fa-heart"
          }
          if (otherText) {
            otherText.textContent = isActive ? "В избранном" : "В избранное"
          }
        }
      })

      // Анимация удаления на странице избранного
      if (!isActive && window.location.pathname.includes("favorites")) {
        const card = btn.closest(".col-lg-4, .col-md-6, .space-card")
        if (card) {
          card.style.transition = "opacity 0.4s, transform 0.4s"
          card.style.opacity = "0"
          card.style.transform = "translateY(20px)"
          setTimeout(() => {
            card.remove()
            if (document.querySelectorAll(".space-card").length === 0) {
              location.reload()
            }
          }, 400)
        }
      }
    } catch (err) {
      console.error("Ошибка избранного:", err)
      showNotification("Не удалось обновить избранное", "danger")
      btn.classList.toggle("active", wasActive)
    } finally {
      btn.disabled = false
      btn.style.transform = originalTransform
    }
  })
}

// =============================
// ФОРМА ОТЗЫВОВ
// =============================

function initReviewForm() {
  const starRating = document.getElementById("starRating")
  const ratingValue = document.getElementById("ratingValue")
  const reviewForm = document.getElementById("reviewForm")

  if (starRating && ratingValue) {
    starRating.querySelectorAll('input[type="radio"]').forEach((input) => {
      input.addEventListener("change", () => (ratingValue.value = input.value))
    })
    starRating.querySelectorAll("label").forEach((label) => {
      label.addEventListener("click", () => {
        const forAttr = label.getAttribute("for")
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
      if (!ratingValue?.value) {
        e.preventDefault()
        showNotification("Выберите оценку", "warning")
      }
    })
  }
}

// =============================
// УЛУЧШЕНИЯ ФОРМ
// =============================

function initFormEnhancements() {
  document.querySelectorAll(".form-control, .form-select").forEach((el) => {
    el.addEventListener("focus", () => el.closest(".mb-3, .form-group")?.classList.add("input-focused"))
    el.addEventListener("blur", () => el.closest(".mb-3, .form-group")?.classList.remove("input-focused"))
  })

  document.querySelectorAll("textarea").forEach((el) => {
    const onInput = () => {
      el.style.height = "auto"
      el.style.height = Math.min(el.scrollHeight, 300) + "px"
    }
    el.addEventListener("input", onInput)
    onInput() // Инициализация
  })

  const codeInput = document.getElementById("id_code")
  if (codeInput) {
    codeInput.focus()
    codeInput.addEventListener("input", (e) => {
      e.target.value = e.target.value.replace(/\D/g, "")
      if (e.target.value.length === 6) {
        document.getElementById("verifyCodeForm")?.submit()
      }
    })
  }
}

// =============================
// АНИМАЦИИ
// =============================

function initButtonAnimations() {
  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return

  document.querySelectorAll(".btn:not(.btn-gold):not(.btn-outline-gold)").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      const rect = btn.getBoundingClientRect()
      const x = e.clientX - rect.left
      const y = e.clientY - rect.top

      const ripple = document.createElement("span")
      ripple.style.cssText = `
        position: absolute; top: ${y}px; left: ${x}px;
        width: 100px; height: 100px;
        background: rgba(255,255,255,0.3);
        border-radius: 50%;
        transform: scale(0);
        animation: ripple 0.6s linear;
        pointer-events: none;
      `
      btn.style.position = "relative"
      btn.style.overflow = "hidden"
      btn.appendChild(ripple)
      setTimeout(() => ripple.remove(), 600)
    })
  })

  if (!document.getElementById("ripple-styles")) {
    const style = document.createElement("style")
    style.id = "ripple-styles"
    style.textContent = `@keyframes ripple { to { transform: scale(4); opacity: 0; } }`
    document.head.appendChild(style)
  }
}

function initScrollAnimations() {
  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return
  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry, i) => {
        if (entry.isIntersecting) {
          setTimeout(() => entry.target.classList.add("animate-fade-in"), i * 50)
          observer.unobserve(entry.target)
        }
      })
    },
    { threshold: 0.1, rootMargin: "0px 0px -50px 0px" },
  )

  document.querySelectorAll(".space-card, .dashboard-card, .glass-card").forEach((el) => {
    el.classList.add("animate-prepare")
    observer.observe(el)
  })
}

function initSmoothScroll() {
  document.querySelectorAll('a[href^="#"]').forEach((link) => {
    link.addEventListener("click", (e) => {
      const target = document.querySelector(link.getAttribute("href"))
      if (target) {
        e.preventDefault()
        target.scrollIntoView({ behavior: "smooth", block: "start" })
      }
    })
  })
}

// =============================
// ЭКСПОРТ
// =============================

window.InteriorApp = { showNotification, formatPrice, getCsrfToken }
