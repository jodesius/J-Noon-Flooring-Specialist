/* Availability calendar on the Contact page - a plain month view, no
 * external library. Renders from the booked-dates list the server sends
 * down in #availability-calendar's data-booked attribute (a JSON array
 * of "YYYY-MM-DD" strings); Prev/Next just redraw client-side, no
 * further requests. Purely informational, not a date picker - nothing
 * is clickable except the month navigation. */
(function () {
    "use strict";

    var container = document.getElementById("availability-calendar");
    if (!container) return;

    var booked = new Set();
    try {
        JSON.parse(container.dataset.booked || "[]").forEach(function (d) {
            booked.add(d);
        });
    } catch (e) {
        // malformed/missing data - render with nothing booked rather than break
    }

    var today = new Date();
    today.setHours(0, 0, 0, 0);
    var viewYear = today.getFullYear();
    var viewMonth = today.getMonth();

    var MONTH_NAMES = [
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December",
    ];
    var WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

    function toISO(date) {
        var y = date.getFullYear();
        var m = String(date.getMonth() + 1).padStart(2, "0");
        var d = String(date.getDate()).padStart(2, "0");
        return y + "-" + m + "-" + d;
    }

    function render() {
        container.innerHTML = "";

        var header = document.createElement("div");
        header.className = "availability-cal__header";

        var prevBtn = document.createElement("button");
        prevBtn.type = "button";
        prevBtn.className = "availability-cal__nav";
        prevBtn.textContent = "‹";
        prevBtn.setAttribute("aria-label", "Previous month");
        var isCurrentMonth = (
            viewYear === today.getFullYear() && viewMonth === today.getMonth()
        );
        prevBtn.disabled = isCurrentMonth;

        var monthLabel = document.createElement("span");
        monthLabel.className = "availability-cal__month";
        monthLabel.textContent = MONTH_NAMES[viewMonth] + " " + viewYear;

        var nextBtn = document.createElement("button");
        nextBtn.type = "button";
        nextBtn.className = "availability-cal__nav";
        nextBtn.textContent = "›";
        nextBtn.setAttribute("aria-label", "Next month");

        header.appendChild(prevBtn);
        header.appendChild(monthLabel);
        header.appendChild(nextBtn);
        container.appendChild(header);

        var grid = document.createElement("div");
        grid.className = "availability-cal__grid";

        WEEKDAYS.forEach(function (wd) {
            var cell = document.createElement("div");
            cell.className = "availability-cal__weekday";
            cell.textContent = wd;
            grid.appendChild(cell);
        });

        var firstOfMonth = new Date(viewYear, viewMonth, 1);
        var startOffset = (firstOfMonth.getDay() + 6) % 7;  // Monday-first
        var daysInMonth = new Date(viewYear, viewMonth + 1, 0).getDate();

        for (var i = 0; i < startOffset; i++) {
            var blank = document.createElement("div");
            blank.className = "availability-cal__day availability-cal__day--blank";
            grid.appendChild(blank);
        }

        for (var day = 1; day <= daysInMonth; day++) {
            var date = new Date(viewYear, viewMonth, day);
            var cell = document.createElement("div");
            cell.className = "availability-cal__day";
            cell.textContent = String(day);

            if (date < today) {
                cell.classList.add("availability-cal__day--past");
            } else if (booked.has(toISO(date))) {
                cell.classList.add("availability-cal__day--booked");
            }
            if (date.getTime() === today.getTime()) {
                cell.classList.add("availability-cal__day--today");
            }
            grid.appendChild(cell);
        }

        container.appendChild(grid);

        prevBtn.addEventListener("click", function () {
            if (prevBtn.disabled) return;
            viewMonth -= 1;
            if (viewMonth < 0) {
                viewMonth = 11;
                viewYear -= 1;
            }
            render();
        });
        nextBtn.addEventListener("click", function () {
            viewMonth += 1;
            if (viewMonth > 11) {
                viewMonth = 0;
                viewYear += 1;
            }
            render();
        });
    }

    render();
})();
