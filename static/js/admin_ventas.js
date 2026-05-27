function toggleDetails(ventaId) {
    const detailsRow = document.getElementById(`details-${ventaId}`);
    const icon = document.querySelector(`.venta-row[data-venta-id='${ventaId}'] .expand-btn i`);

    if (detailsRow.classList.contains('visible')) {
        detailsRow.classList.remove('visible');
        icon.classList.remove('fa-chevron-up');
        icon.classList.add('fa-chevron-down');
    } else {
        document.querySelectorAll('.details-row.visible').forEach(row => {
            row.classList.remove('visible');
            const otherIcon = document.querySelector(`.venta-row[data-venta-id='${row.id.split('-')[1]}'] .expand-btn i`);
            if(otherIcon) {
                otherIcon.classList.remove('fa-chevron-up');
                otherIcon.classList.add('fa-chevron-down');
            }
        });

        detailsRow.classList.add('visible');
        icon.classList.remove('fa-chevron-down');
        icon.classList.add('fa-chevron-up');
    }
}