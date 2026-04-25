'use strict';

document.addEventListener('DOMContentLoaded', () => {
    const configNode = document.getElementById('members-config');
    if (!configNode) {
        return;
    }

    const config = JSON.parse(configNode.textContent);
    const addMemberButton = document.getElementById('btnAddMember');
    const addUserSelect = document.getElementById('addUserId');
    const addRoleSelect = document.getElementById('addRole');
    const statusNode = document.getElementById('membersPageStatus');
    const addMemberModalNode = document.getElementById('addMemberModal');
    const addMemberModal = addMemberModalNode && window.bootstrap
        ? window.bootstrap.Modal.getOrCreateInstance(addMemberModalNode)
        : null;

    const showStatus = (message, state) => {
        if (!statusNode) {
            return;
        }

        statusNode.textContent = message;
        statusNode.dataset.state = state;
        statusNode.hidden = !message;
    };

    const readErrorMessage = async (response, fallbackMessage) => {
        try {
            const payload = await response.json();
            return payload.error || fallbackMessage;
        } catch (error) {
            return fallbackMessage;
        }
    };

    const handleAddMember = async () => {
        const userId = Number.parseInt(addUserSelect?.value || '', 10);
        const role = addRoleSelect?.value || 'viewer';

        if (!Number.isInteger(userId)) {
            showStatus(config.selectUserMessage, 'error');
            addUserSelect?.focus();
            return;
        }

        showStatus('', 'success');
        addMemberButton.disabled = true;

        try {
            const response = await fetch(config.membersUrl, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ user_id: userId, role }),
            });

            if (!response.ok) {
                throw new Error(await readErrorMessage(response, config.saveFailedMessage));
            }

            addMemberModal?.hide();
            window.location.reload();
        } catch (error) {
            showStatus(error.message || config.saveFailedMessage, 'error');
        } finally {
            addMemberButton.disabled = false;
        }
    };

    const handleRemoveMember = async (button) => {
        const memberId = button.dataset.memberId;
        if (!memberId) {
            return;
        }

        if (!window.confirm(config.confirmRemove)) {
            return;
        }

        showStatus('', 'success');
        button.disabled = true;

        try {
            const response = await fetch(`${config.membersUrl}/${memberId}`, { method: 'DELETE' });
            if (!response.ok && response.status !== 204) {
                throw new Error(await readErrorMessage(response, config.removeFailedMessage));
            }

            window.location.reload();
        } catch (error) {
            showStatus(error.message || config.removeFailedMessage, 'error');
            button.disabled = false;
        }
    };

    addMemberButton?.addEventListener('click', () => {
        void handleAddMember();
    });

    document.addEventListener('click', (event) => {
        const removeButton = event.target.closest('.remove-member-btn');
        if (!removeButton) {
            return;
        }

        void handleRemoveMember(removeButton);
    });

    addMemberModalNode?.addEventListener('hidden.bs.modal', () => {
        showStatus('', 'success');
        if (addUserSelect) {
            addUserSelect.value = '';
        }
        if (addRoleSelect) {
            addRoleSelect.value = 'viewer';
        }
    });
});
