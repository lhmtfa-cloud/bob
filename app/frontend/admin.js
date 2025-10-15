document.addEventListener('DOMContentLoaded', function() {
    const token = localStorage.getItem('accessToken');
    if (!token) {
        window.location.href = '/login';
        return;
    }

    initializeAdminDarkMode();

    const headers = {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
    };

    async function verifyAdminAccess() {
        try {
            const response = await fetch('/users/me', { headers });
            if (!response.ok) {
                throw new Error('Falha na autenticação');
            }
            const user = await response.json();
            if (user.role !== 'admin' && user.role !== 'superuser') {
                alert('Acesso negado. Você não tem permissão para ver esta página.');
                window.location.href = '/app';
                throw new Error('Permissão insuficiente');
            }
            loadDashboard();
        } catch (error) {
            console.error(error.message);
            localStorage.removeItem('accessToken');
            if (!window.location.pathname.endsWith('/login')) {
                window.location.href = '/login';
            }
        }
    }

    function loadDashboard() {
        fetchAdminData();
        fetchUsers();
    }

    function fetchAdminData() {
        fetch('/admin/dashboard', { headers })
            .then(response => response.json())
            .then(data => {
                populateStatsTable(data.user_stats);
                populateUploadsTable(data.recent_uploads);
            })
            .catch(err => console.error("Failed to load dashboard data:", err));
    }

    function fetchUsers() {
        fetch('/admin/users', { headers })
            .then(response => response.json())
            .then(populateUsersTable)
            .catch(err => console.error("Failed to load users:", err));
    }

    function populateStatsTable(stats) {
        const tbody = document.querySelector('#stats-table tbody');
        tbody.innerHTML = '';
        if (!stats || stats.length === 0) {
            const row = tbody.insertRow();
            const cell = row.insertCell();
            cell.colSpan = 4;
            cell.textContent = 'Nenhuma estatística de uso encontrada.';
            cell.style.textAlign = 'center';
            return;
        }
        stats.forEach(stat => {
            const row = tbody.insertRow();
            row.innerHTML = `
                <td>${stat.user ? stat.user.username : 'Utilizador Apagado'}</td>
                <td>${stat.files_uploaded_count || 0}</td>
                <td>${stat.request_count || 0}</td>
                <td>${stat.last_activity ? new Date(stat.last_activity).toLocaleString('pt-BR') : 'N/A'}</td>
            `;
        });
    }

    function populateUploadsTable(uploads) {
        const tbody = document.querySelector('#uploads-table tbody');
        tbody.innerHTML = '';
        if (!uploads || uploads.length === 0) {
            const row = tbody.insertRow();
            const cell = row.insertCell();
            cell.colSpan = 5;
            cell.textContent = 'Nenhum upload nas últimas 24 horas.';
            cell.style.textAlign = 'center';
            return;
        }
        uploads.forEach(upload => {
            const row = tbody.insertRow();
            const downloadLink = upload.status === 'finished' 
                ? `<a href="#" class="download-zip-link" data-code="${upload.tracking_code}">Download</a>`
                : 'N/A';
            row.innerHTML = `
                <td>${upload.owner ? upload.owner.username : 'Utilizador Apagado'}</td>
                <td>${upload.original_filename || 'N/A'}</td>
                <td>${upload.upload_time ? new Date(upload.upload_time).toLocaleString('pt-BR') : 'N/A'}</td>
                <td>${upload.status || 'N/A'}</td>
                <td>${downloadLink}</td>
            `;
        });
    }
    
    function populateUsersTable(users) {
        const tbody = document.querySelector('#users-table tbody');
        tbody.innerHTML = '';
        if(!users) return;
        users.forEach(user => {
            const row = tbody.insertRow();
            const deleteBtn = `<button class="delete-btn" data-id="${user.id}">Deletar</button>`;
            const promoteSelect = `
                <select class="role-select" data-id="${user.id}">
                    <option value="user" ${user.role === 'user' ? 'selected' : ''}>Utilizador</option>
                    <option value="admin" ${user.role === 'admin' ? 'selected' : ''}>Admin</option>
                </select>`;
            
            row.innerHTML = `
                <td>${user.username}</td>
                <td>${user.role === 'superuser' ? 'Superuser' : promoteSelect}</td>
                <td>${new Date(user.created_at).toLocaleDateString('pt-BR')}</td>
                <td>${user.role !== 'superuser' ? deleteBtn : ''}</td>
            `;
        });
    }

    document.querySelector('#uploads-table').addEventListener('click', e => {
        if (e.target.classList.contains('download-zip-link')) {
            e.preventDefault();
            const code = e.target.dataset.code;
            handleAuthenticatedDownload(`/download/zip/${code}`, `processado_${code}.zip`);
        }
    });

    document.querySelector('#users-table').addEventListener('click', e => {
        if (e.target.classList.contains('delete-btn')) {
            const userId = e.target.dataset.id;
            if (confirm('Tem certeza que deseja deletar este utilizador?')) {
                deleteUser(userId);
            }
        }
    });
    
    document.querySelector('#users-table').addEventListener('change', e => {
        if (e.target.classList.contains('role-select')) {
            const userId = e.target.dataset.id;
            const newRole = e.target.value;
            if (confirm(`Tem certeza que deseja mudar o papel deste utilizador para ${newRole}?`)) {
                updateUserRole(userId, newRole);
            }
        }
    });

    document.getElementById('create-user-btn').addEventListener('click', () => {
        const username = document.getElementById('new-username').value;
        const password = document.getElementById('new-password').value;
        const role = document.getElementById('new-user-role').value;
        const apiKey = document.getElementById('new-api-key').value;

        if (!username || !password) {
            alert('Nome de utilizador e palavra-passe são obrigatórios.');
            return;
        }

        const userData = { username, password, role };
        if (apiKey) {
            userData.api_key = apiKey;
        }

        fetch('/admin/users', {
            method: 'POST',
            headers,
            body: JSON.stringify(userData)
        })
        .then(response => {
            if (!response.ok) {
                return response.json().then(err => { throw new Error(err.detail || 'Falha ao criar utilizador.') });
            }
            return response.json();
        })
        .then(() => {
            alert('Utilizador criado com sucesso!');
            fetchUsers();
            document.getElementById('new-username').value = '';
            document.getElementById('new-password').value = '';
            document.getElementById('new-api-key').value = '';
        })
        .catch(err => alert(err.message));
    });

    function deleteUser(userId) {
        fetch(`/admin/users/${userId}`, { method: 'DELETE', headers })
            .then(response => {
                if (!response.ok) {
                    return response.json().then(err => { throw new Error(err.detail || 'Não foi possível apagar o utilizador.') });
                }
                alert('Utilizador apagado com sucesso.');
                fetchUsers();
                fetchAdminData();
            })
            .catch(err => alert(err.message));
    }
    
    function updateUserRole(userId, role) {
        fetch(`/admin/users/${userId}/role`, { 
            method: 'PUT',
            headers,
            body: JSON.stringify({ role })
        })
        .then(response => {
            if (!response.ok) {
                return response.json().then(err => { throw new Error(err.detail || 'Não foi possível alterar o papel do utilizador.') });
            }
            alert('Papel do utilizador alterado com sucesso.');
            fetchUsers();
        })
        .catch(err => {
            alert(err.message);
            fetchUsers();
        });
    }

    async function handleAuthenticatedDownload(url, filename) {
        const token = localStorage.getItem('accessToken');
        try {
            const response = await fetch(url, {
                headers: { 'Authorization': `Bearer ${token}` }
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || `HTTP ${response.status}`);
            }

            const blob = await response.blob();
            const downloadUrl = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.style.display = 'none';
            a.href = downloadUrl;
            a.download = filename;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(downloadUrl);
            a.remove();
        } catch (error) {
            console.error('Erro no download:', error);
            alert(`Falha no download: ${error.message}`);
        }
    }
    
    document.getElementById('logout-button').addEventListener('click', () => {
        localStorage.removeItem('accessToken');
        window.location.href = '/login';
    });

    function initializeAdminDarkMode() {
        const darkModeToggle = document.getElementById('dark-mode-toggle');
        const isDarkMode = localStorage.getItem('darkMode') === 'true';
        if(darkModeToggle) {
            darkModeToggle.checked = isDarkMode;
            if (isDarkMode) {
                document.body.classList.add('dark-mode');
            }
            darkModeToggle.addEventListener('change', function() {
                document.body.classList.toggle('dark-mode');
                localStorage.setItem('darkMode', this.checked);
            });
        }
    }

    verifyAdminAccess();
});