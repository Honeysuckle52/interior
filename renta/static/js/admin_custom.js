/*** Кастомный JavaScript для Django Jazzmin Admin Panel
 * ООО "ИНТЕРЬЕР" - Поддержка переключения светлой/тёмной темы
 * Версия 6.0 - Восстановление кнопки, исправление светлой темы, сохранение дизайна тёмной темы
 */

document.addEventListener("DOMContentLoaded", () => {
    // Создаём кнопку переключения темы
    createThemeToggle();
    // Применяем сохранённую тему
    applySavedTheme();
    // Добавляем анимации при загрузке
    addLoadAnimations();
});

/**
 * Создаёт кнопку переключения темы
 */
function createThemeToggle() {
    // Проверяем, не создана ли уже кнопка
    if (document.getElementById("theme-toggle")) return;

    const toggle = document.createElement("button");
    toggle.className = "theme-toggle";
    toggle.id = "theme-toggle";
    toggle.title = "Переключить тему";
    toggle.setAttribute("aria-label", "Переключить тему");
    toggle.innerHTML = '<i class="fas fa-moon"></i>';
    toggle.addEventListener("click", toggleTheme);
    document.body.appendChild(toggle);
}

/**
 * Переключает между светлой и тёмной темой
 */
function toggleTheme() {
    const body = document.body;
    const toggle = document.getElementById("theme-toggle");
    const isLight = body.classList.contains("light-mode");

    // Добавляем класс для анимации
    body.classList.add("theme-transitioning");

    if (isLight) {
        // Переключаем на тёмную
        body.classList.remove("light-mode");
        body.setAttribute("data-theme", "dark");
        if (toggle) toggle.innerHTML = '<i class="fas fa-moon"></i>';
        localStorage.setItem("admin-theme", "dark");
        updateBootstrapTheme("dark");
    } else {
        // Переключаем на светлую (исправляем для контраста)
        body.classList.add("light-mode");
        body.setAttribute("data-theme", "light");
        if (toggle) toggle.innerHTML = '<i class="fas fa-sun"></i>';
        localStorage.setItem("admin-theme", "light");
        updateBootstrapTheme("light");
    }

    // Убираем класс анимации после завершения перехода
    setTimeout(() => {
        body.classList.remove("theme-transitioning");
    }, 400);
}

/**
 * Применяет сохранённую тему при загрузке
 */
function applySavedTheme() {
    const savedTheme = localStorage.getItem("admin-theme") || "dark";
    const body = document.body;
    const toggle = document.getElementById("theme-toggle");

    if (savedTheme === "light") {
        body.classList.add("light-mode");
        body.setAttribute("data-theme", "light");
        if (toggle) toggle.innerHTML = '<i class="fas fa-sun"></i>';
        updateBootstrapTheme("light");
    } else {
        body.classList.remove("light-mode");
        body.setAttribute("data-theme", "dark");
        if (toggle) toggle.innerHTML = '<i class="fas fa-moon"></i>';
        updateBootstrapTheme("dark");
    }
}

/**
 * Обновляет Bootstrap/AdminLTE классы темы
 */
function updateBootstrapTheme(theme) {
    const navbar = document.querySelector(".main-header.navbar");
    const sidebar = document.querySelector(".main-sidebar");
    const wrapper = document.querySelector(".wrapper");

    if (theme === "light") {
        // Светлая тема
        if (navbar) {
            navbar.classList.remove("navbar-dark");
            navbar.classList.add("navbar-light");
        }
        if (sidebar) {
            sidebar.classList.remove("sidebar-dark-warning");
            sidebar.classList.add("sidebar-light-warning");
        }
    } else {
        // Тёмная тема
        if (navbar) {
            navbar.classList.remove("navbar-light");
            navbar.classList.add("navbar-dark");
        }
        if (sidebar) {
            sidebar.classList.remove("sidebar-light-warning");
            sidebar.classList.add("sidebar-dark-warning");
        }
    }
}

/**
 * Добавляет анимации при загрузке страницы
 */
function addLoadAnimations() {
    // Анимируем карточки
    const cards = document.querySelectorAll(".card, .info-box, .small-box, .stat-card, .chart-card, .data-card");
    cards.forEach((card, index) => {
        card.style.opacity = "0";
        card.style.transform = "translateY(20px)";
        setTimeout(() => {
            card.style.transition = "opacity 0.4s ease, transform 0.4s ease";
            card.style.opacity = "1";
            card.style.transform = "translateY(0)";
        }, 50 + index * 50);
    });
}