/* Edit profile page: instant client-side check + preview for the image.
   The server still re-checks every upload with Pillow - this is only UX. */
(function () {
    "use strict";

    var MAX_BYTES = 1024 * 1024;
    var ALLOWED = ["image/png", "image/jpeg"];

    var input = document.querySelector('input[type="file"]');
    var feedback = document.querySelector("[data-image-feedback]");
    var avatar = document.querySelector(".profile__avatar");
    if (!input || !feedback) {
        return;
    }

    function show(text, kind) {
        feedback.textContent = text;
        feedback.className = "profile__feedback profile__feedback--" + kind;
        feedback.hidden = false;
    }

    input.addEventListener("change", function () {
        feedback.hidden = true;

        var file = input.files && input.files[0];
        if (!file) {
            return;
        }

        if (ALLOWED.indexOf(file.type) === -1 || file.size > MAX_BYTES) {
            show(
                "Upload error - please use the correct format (PNG or JPEG) " +
                "and keep the file size under 1MB.",
                "error"
            );
            input.value = "";
            return;
        }

        show("Looks good - press Save profile to finish the upload.", "ok");

        if (avatar && window.FileReader) {
            var reader = new FileReader();
            reader.onload = function (event) {
                avatar.innerHTML = "";
                var img = document.createElement("img");
                img.alt = "New profile image preview";
                img.src = event.target.result;
                avatar.appendChild(img);
            };
            reader.readAsDataURL(file);
        }
    });
})();
