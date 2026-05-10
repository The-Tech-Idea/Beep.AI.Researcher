(function () {
    'use strict';

    function getConfig() {
        var element = document.getElementById('tasks-config');
        if (!element) {
            return null;
        }

        try {
            return JSON.parse(element.textContent);
        } catch (error) {
            console.error('Failed to parse tasks config.', error);
            return null;
        }
    }

    function getTaskModal() {
        return document.getElementById('taskModal');
    }

    function getModalInstance() {
        var modal = getTaskModal();
        if (!modal) {
            return null;
        }

        return bootstrap.Modal.getOrCreateInstance(modal);
    }

    function buildIconElement(iconName, extraClass) {
        var icon = document.createElement('i');
        icon.className = 'bi bi-' + iconName + ' tasks-button-icon';
        if (extraClass) {
            icon.classList.add(extraClass);
        }
        icon.setAttribute('aria-hidden', 'true');
        return icon;
    }

    function buildLabelElement(text) {
        var label = document.createElement('span');
        label.textContent = text;
        return label;
    }

    function setSuggestButtonContent(button, label, isLoading) {
        if (!button) {
            return;
        }

        var iconName = isLoading ? 'arrow-repeat' : 'stars';
        var iconClass = isLoading ? 'tasks-button-spinner' : '';
        button.replaceChildren(buildIconElement(iconName, iconClass), buildLabelElement(label));
    }

    function getDragAfter(container, y) {
        var cards = Array.prototype.slice.call(container.querySelectorAll('.spa-task-card:not(.dragging)'));
        return cards.reduce(function (closest, child) {
            var box = child.getBoundingClientRect();
            var offset = y - box.top - box.height / 2;
            return (offset < 0 && offset > closest.offset)
                ? { offset: offset, element: child }
                : closest;
        }, { offset: Number.NEGATIVE_INFINITY }).element;
    }

    function updateTaskCounts() {
        document.querySelectorAll('.spa-kanban-col').forEach(function (column) {
            var count = column.querySelectorAll('.spa-task-card').length;
            var badge = column.querySelector('.spa-badge');
            if (badge) {
                badge.textContent = count;
            }
        });
    }

    function resetTaskForm(status, modalTitle) {
        document.getElementById('taskId').value = '';
        document.getElementById('taskStatus').value = status;
        document.getElementById('taskTitle').value = '';
        document.getElementById('taskDescription').value = '';
        document.getElementById('taskPriority').value = 'medium';
        document.getElementById('taskDueDate').value = '';
        document.getElementById('modalTitle').textContent = modalTitle;

        var suggestionPanel = document.querySelector('[data-task-suggestions]');
        if (suggestionPanel) {
            suggestionPanel.remove();
        }
    }

    function bindDragAndDrop(config) {
        var cards = document.querySelectorAll('.spa-task-card');
        var columns = document.querySelectorAll('.spa-kanban-col-body');

        cards.forEach(function (card) {
            card.addEventListener('dragstart', function () {
                card.classList.add('dragging');
            });
            card.addEventListener('dragend', function () {
                card.classList.remove('dragging');
            });
        });

        columns.forEach(function (column) {
            column.addEventListener('dragover', function (event) {
                event.preventDefault();
                var dragging = document.querySelector('.dragging');
                if (!dragging) {
                    return;
                }

                var after = getDragAfter(column, event.clientY);
                if (after) {
                    column.insertBefore(dragging, after);
                } else {
                    column.appendChild(dragging);
                }
            });

            column.addEventListener('drop', function () {
                var dragging = document.querySelector('.dragging');
                if (!dragging) {
                    return;
                }

                var taskId = dragging.dataset.taskId;
                var status = column.closest('.spa-kanban-col').dataset.status;
                if (!taskId || !status) {
                    return;
                }

                fetch(config.taskUpdateUrlTemplate.replace('__TASK_ID__', taskId), {
                    method: 'PATCH',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ status: status })
                })
                    .then(function (response) { return response.json(); })
                    .then(function () {
                        updateTaskCounts();
                    })
                    .catch(function () { /* silently fail — counts will be stale */ });
            });
        });
    }

    function bindTaskFormActions(config) {
        document.querySelectorAll('[data-add-task-status]').forEach(function (button) {
            button.addEventListener('click', function () {
                var status = button.dataset.addTaskStatus || 'todo';
                resetTaskForm(status, config.modalTitle);
                getModalInstance().show();
            });
        });

        var addTaskButton = document.getElementById('addTaskBtn');
        if (addTaskButton) {
            addTaskButton.addEventListener('click', function () {
                resetTaskForm('todo', config.modalTitle);
                getModalInstance().show();
            });
        }

        var saveTaskButton = document.getElementById('saveTaskBtn');
        if (saveTaskButton) {
            saveTaskButton.addEventListener('click', function () {
                var data = {
                    id: document.getElementById('taskId').value || null,
                    status: document.getElementById('taskStatus').value,
                    title: document.getElementById('taskTitle').value,
                    description: document.getElementById('taskDescription').value,
                    priority: document.getElementById('taskPriority').value,
                    due_date: document.getElementById('taskDueDate').value || null
                };

                fetch(config.tasksUrl, {
                    method: data.id ? 'PUT' : 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(data)
                })
                    .then(function (response) { return response.json(); })
                    .then(function () {
                        var modal = getModalInstance();
                        if (modal) {
                            modal.hide();
                        }
                        window.location.reload();
                    })
                    .catch(function () { /* silently fail — user can retry */ });
            });
        }
    }

    function renderSuggestions(config, tasks) {
        if (!tasks || !tasks.length) {
            return;
        }

        var existing = document.querySelector('[data-task-suggestions]');
        if (existing) {
            existing.remove();
        }

        var wrapper = document.createElement('div');
        wrapper.dataset.taskSuggestions = 'true';
        wrapper.className = 'tasks-suggestions-panel';

        var heading = document.createElement('strong');
        heading.className = 'tasks-suggestions-heading';
        heading.textContent = config.suggestPickLabel;
        wrapper.appendChild(heading);

        var list = document.createElement('ul');
        list.className = 'tasks-suggestions-list';

        tasks.forEach(function (taskTitle, index) {
            var item = document.createElement('li');
            item.className = 'tasks-suggestion-list-item';

            var action = document.createElement('button');
            action.type = 'button';
            action.className = 'tasks-suggestion-item';
            action.dataset.title = taskTitle;
            action.textContent = (index + 1) + '. ' + taskTitle;
            action.addEventListener('click', function () {
                document.getElementById('taskTitle').value = action.dataset.title;
                document.getElementById('taskTitle').focus();
                wrapper.remove();
            });

            item.appendChild(action);
            list.appendChild(item);
        });

        wrapper.appendChild(list);
        document.getElementById('taskModalBody').prepend(wrapper);
        document.getElementById('taskStatus').value = 'todo';
        document.getElementById('modalTitle').textContent = config.modalTitle;
        getModalInstance().show();
    }

    function bindSuggestions(config) {
        var suggestButton = document.getElementById('suggestTasksBtn');
        if (!suggestButton) {
            return;
        }

        suggestButton.addEventListener('click', function () {
            suggestButton.disabled = true;
            setSuggestButtonContent(suggestButton, config.suggestLoadingLabel, true);

            fetch(config.suggestTasksUrl, { method: 'POST' })
                .then(function (response) { return response.json(); })
                .then(function (payload) {
                    renderSuggestions(config, payload.tasks || []);
                })
                .catch(function (error) {
                    console.error(error);
                })
                .finally(function () {
                    suggestButton.disabled = false;
                    setSuggestButtonContent(suggestButton, config.suggestTasksLabel, false);
                });
        });
    }

    document.addEventListener('DOMContentLoaded', function () {
        var config = getConfig();
        if (!config) {
            return;
        }

        bindDragAndDrop(config);
        bindTaskFormActions(config);
        bindSuggestions(config);
    });
})();
