'use strict';
document.addEventListener('DOMContentLoaded', () => {
    const byId = id => document.getElementById(id);
    const form = byId('add-expense-form');
    const addButton = byId('add-expense');
    const filterButton = byId('apply-filter');
    const error = byId('error-message');
    const list = byId('expense-list');
    const total = byId('expense-total');
    const money = cents => `CAD $${Math.floor(cents / 100)}.${String(cents % 100).padStart(2, '0')}`;
    function showError(message) {
        error.textContent = message;
        error.hidden = !message;
    }
    async function request(url, options) {
        const response = await fetch(url, options);
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || 'Request failed. Please retry.');
        return data;
    }
    async function refresh() {
        const category = byId('filter-category').value.trim();
        const data = await request(`/api/expenses?category=${encodeURIComponent(category)}`);
        list.replaceChildren();
        for (const expense of data.expenses) {
            const item = document.createElement('li');
            item.dataset.testid = 'expense-item';
            item.textContent = `${expense.date} — ${expense.category} — ${expense.description} — ${money(expense.amount_cents)}`;
            list.append(item);
        }
        total.textContent = money(data.total_cents);
    }
    function cents(text) {
        if (!/^\d+(?:\.\d{1,2})?$/.test(text)) throw new Error('Enter dollars with at most two decimal places.');
        const [whole, fraction = ''] = text.split('.');
        const value = Number(whole) * 100 + Number(fraction.padEnd(2, '0'));
        if (!Number.isSafeInteger(value) || value < 1 || value > 100000000) throw new Error('Enter an amount from CAD $0.01 to CAD $1000000.00.');
        return value;
    }
    form.addEventListener('submit', async event => {
        event.preventDefault();
        showError('');
        addButton.disabled = true;
        filterButton.disabled = true;
        let saved = false;
        try {
            await request('/api/expenses', {
                method: 'POST', headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({date: byId('expense-date').value,
                    category: byId('expense-category').value,
                    description: byId('expense-description').value,
                    amount_cents: cents(byId('expense-amount').value.trim())})
            });
            saved = true;
            form.reset();
            await refresh();
        } catch (failure) {
            showError(saved ? 'Expense saved; refresh failed. Apply Filter to reload without adding it again.' : (failure.message || 'Network error. Please retry.'));
        } finally {
            addButton.disabled = false;
            filterButton.disabled = false;
        }
    });
    filterButton.addEventListener('click', async () => {
        showError('');
        filterButton.disabled = true;
        addButton.disabled = true;
        try { await refresh(); } catch (failure) { showError(failure.message || 'Network error. Please retry.'); }
        finally { filterButton.disabled = false; addButton.disabled = false; }
    });
    addButton.disabled = true;
    refresh().catch(failure => showError(failure.message)).finally(() => { addButton.disabled = false; });
});
