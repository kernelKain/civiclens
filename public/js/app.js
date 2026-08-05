"use strict";

document.addEventListener("DOMContentLoaded", () => {
    const networkStatus = document.querySelector("#network-status");
    const healthCheckInterval = 15000;
    const healthCheckTimeout = 5000;

    if (!networkStatus) {
        return;
    }

    const setOfflineStatus = (isOffline) => {
        networkStatus.hidden = !isOffline;
    };

    const checkServerReachability = async () => {
        // This indicates browser connectivity only; it does not guarantee server availability.
        if (!navigator.onLine) {
            setOfflineStatus(true);
            return;
        }

        const controller = new AbortController();

        const timeoutId = window.setTimeout(() => {
            controller.abort();
        }, healthCheckTimeout);

        try {
            const response = await fetch("/health", {
                method: "GET",
                cache: "no-store",
                signal: controller.signal,
                headers: {
                    Accept: "application/json",
                },
            });

            setOfflineStatus(!response.ok);
        } catch {
            setOfflineStatus(true);
        } finally {
            window.clearTimeout(timeoutId);
        }
    };

    window.addEventListener("offline", () => {
        setOfflineStatus(true);
    });

    window.addEventListener("online", () => {
        void checkServerReachability();
    });

    document.addEventListener("visibilitychange", () => {
        if (document.visibilityState === "visible") {
            void checkServerReachability();
        }
    });

    void checkServerReachability();

    window.setInterval(() => {
        void checkServerReachability();
    }, healthCheckInterval);
});