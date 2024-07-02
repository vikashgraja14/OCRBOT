// js/script.js
const titles = document.querySelectorAll('.group h2');
titles.forEach((title, index) => {
    title.setAttribute('data-index', index + 1);
    title.addEventListener('click', () => {
        // Your click event logic here
    });
});

// Simulate fetching data (replace with actual data retrieval)
window.addEventListener('load', () => {
    setTimeout(() => {
        // Show the table and hide the loading message
        document.getElementById('loading').style.display = 'none';
    }, 2000); // Simulate a delay of 2 seconds (replace with actual data fetching)
});
