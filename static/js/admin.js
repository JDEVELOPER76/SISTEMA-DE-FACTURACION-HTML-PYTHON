const formatoMoneda = new Intl.NumberFormat('es-EC', { style: 'currency', currency: 'USD' });
document.querySelectorAll('.currency-format').forEach(el => {
    const valor = parseFloat(el.textContent) || 0;
    el.textContent = formatoMoneda.format(valor);
});
