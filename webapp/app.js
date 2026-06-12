/**
 * ryu-vision — File Explorer Mini App
 * 
 * Telegram WebApp untuk menjelajah filesystem Windows
 * via bot backend.
 */

// ─── Telegram WebApp API ─────────────────────────────────────────────
const tg = window.Telegram?.WebApp;

if (tg) {
    tg.ready();
    tg.expand();
    tg.disableVerticalSwipes();
}

// ─── State ───────────────────────────────────────────────────────────
const state = {
    currentPath: 'C:\\',
    history: ['C:\\'],
    historyIdx: 0,
    view: 'files', // 'files' | 'drives'
    loading: false,
};

// ─── Config ──────────────────────────────────────────────────────────
const CONFIG = {
    // API endpoint relatif — otomatis pake domain yang sama (ngrok)
    apiBase: '',
};

// Override dari Telegram init data jika ada
try {
    const params = new URLSearchParams(window.location.search);
    if (params.get('api')) CONFIG.apiBase = params.get('api');
} catch (e) {}

// ─── Utility ─────────────────────────────────────────────────────────
function getInitData() {
    if (tg?.initData) return tg.initData;
    // Fallback untuk development (tanpa Telegram)
    return 'dev_mode=1';
}

function ipc(endpoint, payload = {}) {
    return fetch(`${CONFIG.apiBase}/api/${endpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            ...payload,
            init_data: getInitData(),
        }),
    }).then(r => r.json());
}

function escapeHtml(str) {
    const d = document.createElement('div');
    d.textContent = str;
    return d.innerHTML;
}

function formatDate(iso) {
    if (!iso) return '';
    const d = new Date(iso);
    return d.toLocaleDateString('id-ID', {
        day: 'numeric', month: 'short', year: 'numeric',
        hour: '2-digit', minute: '2-digit'
    });
}

function fileIcon(item) {
    if (item.is_dir) return '📁';
    const ext = (item.name || '').split('.').pop().toLowerCase();
    const icons = {
        txt: '📄', md: '📝', json: '📋', py: '🐍',
        js: '📜', html: '🌐', css: '🎨', xml: '📰',
        pdf: '📕', doc: '📘', docx: '📘', xls: '📗', xlsx: '📗',
        zip: '📦', rar: '📦', '7z': '📦', gz: '📦',
        exe: '⚙️', dll: '🔧', msi: '📦',
        jpg: '🖼️', jpeg: '🖼️', png: '🖼️', gif: '🖼️', webp: '🖼️',
        mp3: '🎵', wav: '🎵', mp4: '🎬', mkv: '🎬',
        bat: '📟', ps1: '📟', sh: '📟',
    };
    return icons[ext] || '📄';
}

function showToast(msg, duration = 2500) {
    const t = document.getElementById('toast');
    t.textContent = msg;
    t.classList.remove('hidden');
    clearTimeout(t._timer);
    t._timer = setTimeout(() => t.classList.add('hidden'), duration);
}

function setLoading(v) {
    state.loading = v;
    document.getElementById('btn-refresh').textContent = v ? '⏳' : '🔄';
}

// ─── Render Breadcrumb ───────────────────────────────────────────────
function renderBreadcrumb(path) {
    const nav = document.getElementById('breadcrumb');
    if (!path) {
        nav.innerHTML = '<span class="crumb-loading">💾 Pilih drive</span>';
        return;
    }

    const parts = path.replace(/\\/g, '/').split('/').filter(Boolean);
    const crumbs = [];

    // Root / drive
    const drive = path.match(/^[A-Za-z]:/)?.[0] || '';
    if (drive) {
        crumbs.push({ label: drive, path: drive + '\\' });
    }

    let acc = drive ? drive + '\\' : '';
    for (const p of parts) {
        if (p.includes(':')) continue; // skip C: D: etc
        acc += p + '\\';
        crumbs.push({ label: p, path: acc });
    }

    nav.innerHTML = crumbs.map((c, i) => {
        const isLast = i === crumbs.length - 1;
        const sep = i > 0 ? '<span class="crumb-sep">›</span>' : '';
        const cls = isLast ? 'crumb crumb-current' : 'crumb';
        return `${sep}<span class="${cls}" data-path="${escapeHtml(c.path)}">${escapeHtml(c.label)}</span>`;
    }).join('');

    // Click handlers
    nav.querySelectorAll('.crumb:not(.crumb-current)').forEach(el => {
        el.addEventListener('click', () => navigateTo(el.dataset.path));
    });
}

// ─── Render File List ────────────────────────────────────────────────
function renderFileList(data) {
    const list = document.getElementById('file-list');
    const status = document.getElementById('status-bar');

    if (data.error) {
        list.innerHTML = `<div class="empty-state">❌ ${escapeHtml(data.error)}</div>`;
        status.textContent = 'Error';
        return;
    }

    if (!data.items || data.items.length === 0) {
        list.innerHTML = '<div class="empty-state">📂 Folder kosong</div>';
        status.textContent = '0 items';
        return;
    }

    let html = '';
    for (const item of data.items) {
        const icon = item.is_dir ? '📁' : fileIcon(item);
        const errorClass = item.error ? ' file-error' : '';

        html += `
            <div class="file-entry${errorClass}" data-path="${escapeHtml(item.path)}" data-dir="${item.is_dir}">
                <div class="file-icon ${item.is_dir ? 'folder' : ''}">${icon}</div>
                <div class="file-info">
                    <div class="file-name">${escapeHtml(item.name)}</div>
                    <div class="file-meta">
                        ${item.is_dir ? '<span>Folder</span>' : `<span>${item.size_fmt || ''}</span>`}
                        ${item.modified ? `<span>${formatDate(item.modified)}</span>` : ''}
                    </div>
                    ${item.error ? `<div class="file-error-msg">${escapeHtml(item.error)}</div>` : ''}
                </div>
            </div>
        `;
    }

    list.innerHTML = html;
    status.textContent = `${data.item_count} items`;

    // Click handler
    list.querySelectorAll('.file-entry:not(.file-error)').forEach(el => {
        el.addEventListener('click', () => {
            const path = el.dataset.path;
            if (el.dataset.dir === 'true') {
                navigateTo(path);
            } else {
                // File — tampilkan info
                showToast(`📄 ${el.querySelector('.file-name')?.textContent || path}`);
            }
        });
    });
}

// ─── Render Drives ───────────────────────────────────────────────────
function renderDrives(drivesData) {
    const list = document.getElementById('file-list');
    const status = document.getElementById('status-bar');
    const breadcrumb = document.getElementById('breadcrumb');

    breadcrumb.innerHTML = '<span class="crumb crumb-current">💾 Drives</span>';
    state.view = 'drives';

    if (!drivesData.drives || drivesData.drives.length === 0) {
        list.innerHTML = '<div class="empty-state">💾 Tidak ada drive</div>';
        status.textContent = 'No drives';
        return;
    }

    let html = '<div class="drive-grid">';
    for (const d of drivesData.drives) {
        html += `
            <div class="drive-btn" data-drive="${escapeHtml(d.drive)}">
                <div class="drive-icon">💾</div>
                <div class="drive-label">${escapeHtml(d.label || d.drive)}</div>
            </div>
        `;
    }
    html += '</div>';
    list.innerHTML = html;
    status.textContent = `${drivesData.drives.length} drives`;

    list.querySelectorAll('.drive-btn').forEach(el => {
        el.addEventListener('click', () => {
            navigateTo(el.dataset.drive);
        });
    });
}

// ─── Navigation ──────────────────────────────────────────────────────
function navigateTo(path) {
    if (state.loading) return;

    state.currentPath = path;
    state.view = 'files';

    // Push to history
    if (state.history[state.historyIdx] !== path) {
        state.history = state.history.slice(0, state.historyIdx + 1);
        state.history.push(path);
        state.historyIdx = state.history.length - 1;
    }

    renderBreadcrumb(path);
    loadDirectory(path);
}

function goBack() {
    if (state.historyIdx > 0) {
        state.historyIdx--;
        navigateTo(state.history[state.historyIdx]);
    }
}

function goForward() {
    if (state.historyIdx < state.history.length - 1) {
        state.historyIdx++;
        navigateTo(state.history[state.historyIdx]);
    }
}

// ─── Load Directory ──────────────────────────────────────────────────
async function loadDirectory(path) {
    setLoading(true);
    const list = document.getElementById('file-list');
    list.innerHTML = '<div class="loading">⏳ Memuat...</div>';

    try {
        const data = await ipc('ls', { path });
        renderFileList(data);
    } catch (err) {
        list.innerHTML = `<div class="empty-state">❌ Gagal: ${escapeHtml(err.message)}</div>`;
        showToast('Gagal memuat direktori');
    } finally {
        setLoading(false);
    }
}

// ─── Load Drives ─────────────────────────────────────────────────────
async function loadDrives() {
    setLoading(true);
    const list = document.getElementById('file-list');
    list.innerHTML = '<div class="loading">⏳ Memuat drive...</div>';

    try {
        const data = await ipc('drives');
        renderDrives(data);
    } catch (err) {
        list.innerHTML = `<div class="empty-state">❌ Gagal: ${escapeHtml(err.message)}</div>`;
        showToast('Gagal memuat drive');
    } finally {
        setLoading(false);
    }
}

// ─── Init ────────────────────────────────────────────────────────────
async function init() {
    // Show startup info
    if (tg) {
        const user = tg.initDataUnsafe?.user;
        if (user) {
            console.log(`👤 ${user.first_name} (ID: ${user.id})`);
        }
    }

    // Load drives first
    await loadDrives();
}

// ─── Event Listeners ─────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    init();
});

document.getElementById('btn-drives').addEventListener('click', () => {
    loadDrives();
});

document.getElementById('btn-refresh').addEventListener('click', () => {
    if (state.view === 'drives') loadDrives();
    else loadDirectory(state.currentPath);
});

// Keyboard: Backspace = back
document.addEventListener('keydown', (e) => {
    if (e.key === 'Backspace' && !e.target.matches('input, textarea')) {
        e.preventDefault();
        loadDrives(); // back to drives
    }
});
