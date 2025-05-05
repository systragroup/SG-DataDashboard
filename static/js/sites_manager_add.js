// Submit the form and create the site
document.getElementById('submitSiteButton').addEventListener('click', () => {
    const form = document.getElementById('formSite');
    const formData = new FormData(form);
    fetch('/sites_manager/create', {
        method: 'POST',
        body: formData,
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'success') {
            window.location.href = `/site/${data.site}`
        }
    });
});