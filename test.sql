SELECT symbol, SUM(shares) as total_shares FROM purchases WHERE user_id = 3 GROUP BY symbol HAVING total_shares > 0;
