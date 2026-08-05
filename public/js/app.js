"use strict";

document.addEventListener("DOMContentLoaded", () => {
    const networkStatus = document.querySelector("#network-status");

    if (!networkStatus) {
        return;
    }

    // Browser connectivity is only a hint; it does not guarantee server availability.
    const updateNetworkStatus = () => {
        networkStatus.hidden = navigator.onLine;
    };

    window.addEventListener("online", updateNetworkStatus);
    window.addEventListener("offline", updateNetworkStatus);

    updateNetworkStatus();
});