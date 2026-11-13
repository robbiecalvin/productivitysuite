document.addEventListener('DOMContentLoaded', function() {
    const form = document.getElementById('add-expense-form');
    const categoryFilter = document.getElementById('filter-category');
    const applyFilterButton = document.getElementById('apply-filter');
    const expenseList = document.getElementById('expense-list');
    const expenseTotal = document.getElementById('expense-total');
    const errorMessage = document.getElementById('error-message');

    form.addEventListener('submit', function(event) {
        event.preventDefault();
        addExpense();
    });

    applyFilterButton.addEventListener('click', function() {
        updateExpenses(categoryFilter.value.trim());
    });

    function addExpense() {
        const date = document.getElementById('expense-date').value;
        const category = document.getElementById('expense-category').value.trim();
        const description = document.getElementById('expense-description').value.trim().slice(0, 1000);
        const amount = document.getElementById('expense-amount').value;

        fetch('/api/expenses', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ date, category, description, amount_cents: Math.round(amount * 100) })
        }).then(response => response.json())
          .then(data => {
              if (data.error) {
                  errorMessage.textContent = data.error;
                  errorMessage.classList.add('visible');
              } else {
                  updateExpenses(categoryFilter.value.trim());
                  form.reset();
              }
          });
    }

    function updateExpenses(category) {
        fetch(`/api/expenses?category=${encodeURIComponent(category)}`, {
            method: 'GET'
        }).then(response => response.json())
          .then(data => {
              expenseList.innerHTML = '';
              data.expenses.forEach(expense => {
                  const li = document.createElement('li');
                  li.textContent = `${expense.date} - ${expense.category}: $${(expense.amount_cents / 100).toFixed(2)} - ${expense.description}`;
                  expenseList.appendChild(li);
              });
              expenseTotal.textContent = `$${(data.total_cents / 100).toFixed(2)}`;
          }).catch(error => {
              errorMessage.textContent = 'Network error, please try again.';
              errorMessage.classList.add('visible');
          });
    }

    updateExpenses('');
});