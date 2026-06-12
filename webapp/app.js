// ryu-vision — Telegram Mini App
const tg = window.Telegram?.WebApp;

if (tg) {
    tg.ready();
    tg.expand();

    // Tampilkan user info
    const user = tg.initDataUnsafe?.user;
    if (user) {
        document.getElementById('user-name').textContent =
            `${user.first_name || ''} ${user.last_name || ''}`.trim() || 'Pengguna';
    }
}

// Tombol aksi
document.getElementById('btn-action').addEventListener('click', async () => {
    const resultDiv = document.getElementById('result');
    const resultText = document.getElementById('result-text');

    resultDiv.classList.remove('hidden');
    resultText.textContent = 'Memproses...';

    // Kirim data ke bot (contoh)
    if (tg) {
        tg.sendData(JSON.stringify({ action: 'capture' }));
    }

    resultText.textContent = '✅ Data terkirim ke bot!';
});
