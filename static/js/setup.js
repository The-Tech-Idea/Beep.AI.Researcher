(function () {
    var validatedUri = "";
    var adminUsername = "";
    var authMode = "local";

    function byId(id) {
        return document.getElementById(id);
    }

    function notify(message, variant) {
        if (message) {
            window.beepUI.notify(message, { variant: variant || "danger" });
        }
    }

    function setHidden(element, hidden) {
        if (element) {
            element.hidden = hidden;
        }
    }

    function toggleDbFields() {
        var provider = byId("dbProvider").value;
        var externalDbFields = byId("externalDbFields");
        var cosmosDbInfo = byId("cosmosDbInfo");
        var dbPort = byId("dbPort");
        var ports = {
            postgresql: 5432,
            mysql: 3306,
            sqlserver: 1433,
            cosmosdb: 5432
        };

        setHidden(externalDbFields, provider === "sqlite");
        cosmosDbInfo.classList.toggle("d-none", provider !== "cosmosdb");

        if (ports[provider] && dbPort) {
            dbPort.value = ports[provider];
        }
    }

    function showStep(step) {
        var index;
        for (index = 1; index <= 4; index += 1) {
            setHidden(byId("step" + index), index !== step);
        }

        for (index = 1; index <= 4; index += 1) {
            var indicator = byId("step" + index + "-indicator");
            if (!indicator) {
                continue;
            }

            indicator.className = "step";
            if (index === step) {
                indicator.classList.add("active");
                indicator.textContent = String(index);
            } else if (index < step) {
                indicator.classList.add("completed");
                indicator.innerHTML = '<i class="bi bi-check-lg"></i>';
            } else {
                indicator.textContent = String(index);
            }
        }
    }

    function goToStep2() {
        var user = byId("adminUser").value.trim();
        var password = byId("adminPass").value;
        var passwordConfirm = byId("adminPassConfirm").value;

        if (!user || !password) {
            notify("Enter an administrator username and password.");
            return;
        }

        if (password.length < 4) {
            notify("Use a password with at least 4 characters.");
            return;
        }

        if (password !== passwordConfirm) {
            notify("The passwords do not match.");
            return;
        }

        adminUsername = user;
        byId("summaryUser").innerText = user;
        showStep(2);
    }

    async function validateAndNext() {
        var provider = byId("dbProvider").value;
        var errorElement = byId("dbError");
        var nextButton = byId("setupDatabaseNextButton");
        var data = {
            provider: provider,
            host: byId("dbHost").value,
            port: byId("dbPort").value,
            user: byId("dbUser").value,
            password: byId("dbPass").value,
            dbname: byId("dbName").value
        };

        errorElement.classList.add("d-none");
        errorElement.textContent = "";
        window.beepUI.setButtonLoading(nextButton, true, { loadingLabel: "Checking..." });

        try {
            var response = await window.fetch("/setup/api/validate-db", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(data)
            });
            var result = await response.json();

            if (result.success) {
                var names = {
                    sqlite: "SQLite (Embedded)",
                    postgresql: "PostgreSQL",
                    mysql: "MySQL / MariaDB",
                    sqlserver: "SQL Server",
                    cosmosdb: "Azure Cosmos DB"
                };

                validatedUri = result.uri;
                byId("summaryDb").innerText = names[provider] || provider;
                showStep(3);
            } else {
                errorElement.textContent = result.message || "Unable to connect to the database.";
                errorElement.classList.remove("d-none");
            }
        } catch (error) {
            errorElement.textContent = "Unable to connect to the database: " + error.message;
            errorElement.classList.remove("d-none");
        } finally {
            window.beepUI.setButtonLoading(nextButton, false);
        }
    }

    function selectAuthMode(mode) {
        authMode = mode;
        byId("authLocalBtn").classList.toggle("active", mode === "local");
        byId("authIdpBtn").classList.toggle("active", mode === "identity");
        setHidden(byId("identityFields"), mode !== "identity");
    }

    function goToSummary() {
        if (authMode === "identity") {
            var authority = byId("idpAuthority").value;
            var clientId = byId("idpClientId").value;
            if (!authority || !clientId) {
                notify("Enter the service URL and client ID for external sign-in.");
                return;
            }
        }

        byId("summaryAuth").innerText = authMode === "local"
            ? "Built-in sign-in"
            : "External sign-in (OpenID Connect)";
        showStep(4);
    }

    async function finishSetup() {
        var finishButton = byId("finishBtn");
        var data = {
            db_uri: validatedUri,
            username: adminUsername,
            password: byId("adminPass").value,
            email: byId("adminEmail").value || adminUsername + "@localhost",
            auth_mode: authMode,
            identity: {
                authority: byId("idpAuthority").value,
                client_id: byId("idpClientId").value,
                client_secret: byId("idpClientSecret").value,
                scopes: byId("idpScopes").value,
                logout_redirect: byId("idpLogoutRedirect").value
            }
        };

        window.beepUI.setButtonLoading(finishButton, true, { loadingLabel: "Finishing setup..." });

        try {
            var response = await window.fetch("/setup/api/initialize", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(data)
            });
            var result = await response.json();

            if (result.success) {
                window.location.href = result.redirect || "/login";
                return;
            }

            notify("Setup failed: " + (result.message || "Unknown error"));
        } catch (error) {
            notify("Setup error: " + error.message);
        } finally {
            window.beepUI.setButtonLoading(finishButton, false);
        }
    }

    function bindNavigation() {
        byId("setupAdminNextButton").addEventListener("click", goToStep2);
        byId("setupDatabaseBackButton").addEventListener("click", function () { showStep(1); });
        byId("setupDatabaseNextButton").addEventListener("click", validateAndNext);
        byId("setupAuthBackButton").addEventListener("click", function () { showStep(2); });
        byId("setupAuthNextButton").addEventListener("click", goToSummary);
        byId("setupSummaryBackButton").addEventListener("click", function () { showStep(3); });
        byId("finishBtn").addEventListener("click", finishSetup);

        Array.prototype.forEach.call(document.querySelectorAll("[data-auth-mode]"), function (button) {
            button.addEventListener("click", function () {
                selectAuthMode(button.getAttribute("data-auth-mode"));
            });
        });

        byId("dbProvider").addEventListener("change", toggleDbFields);
    }

    document.addEventListener("DOMContentLoaded", function () {
        bindNavigation();
        toggleDbFields();
        selectAuthMode("local");
        showStep(1);
    });
})();
