function confirmDelete() {
    return confirm("Are you sure you want to delete this task?");
}

document.addEventListener("DOMContentLoaded", function () {
    const flashes = document.querySelectorAll(".flash");

    flashes.forEach(function (flash) {
        setTimeout(function () {
            flash.style.opacity = "0";
            flash.style.transform = "translateY(-5px)";

            setTimeout(function () {
                flash.remove();
            }, 300);
        }, 3500);
    });
});
