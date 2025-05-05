// See the site when clicked on
document.addEventListener('DOMContentLoaded', () => {

    fetch('/sites_manager/init')
    .then(response => response.json())
    .then(data => {

        // If there are sites, create one event listener per location
        let hmtl_content = '';
        if (Object.entries(data).length > 0) {
            Object.entries(data).forEach(([key, value]) => {
                document.getElementById(`div${key}`).addEventListener('click', () => {
                    window.location.href = `/site/${key}`
                });
            });
        };

    });
});


// Add location button
document.getElementById('addSiteButton').addEventListener('click', () => {
    window.location.href = '/sites_manager/add'
});