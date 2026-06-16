document.addEventListener('DOMContentLoaded', function() {
    // 1. Auto-dismiss flash message dalam 5 detik
    setTimeout(function() {
        const alerts = document.querySelectorAll('.alert-dismissible');
        alerts.forEach(function(alert) {
            const bsAlert = new bootstrap.Alert(alert);
            bsAlert.close();
        });
    }, 5000);

    // 2. Kalkulasi Estimasi Harga Real-time di Form Transaksi
    const beratInput = document.getElementById('berat');
    const hargaInput = document.getElementById('harga_per_kg');
    const totalInput = document.getElementById('total');

    function calculateTotal() {
        if (beratInput && hargaInput && totalInput) {
            const berat = parseFloat(beratInput.value) || 0;
            const harga = parseFloat(hargaInput.value) || 0;
            const total = berat * harga;
            
            // Format format Rupiah untuk tampilan visual
            totalInput.value = 'Rp ' + total.toLocaleString('id-ID', { minimumFractionDigits: 0 });
        }
    }

    if (beratInput && hargaInput) {
        beratInput.addEventListener('input', calculateTotal);
        hargaInput.addEventListener('input', calculateTotal);
        calculateTotal(); // Jalankan sekali saat load jika dalam mode edit
    }
});