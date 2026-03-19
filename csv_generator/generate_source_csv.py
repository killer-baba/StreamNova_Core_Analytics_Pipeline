import pandas as pd
import numpy as np
from faker import Faker
import random
import argparse
import os
import json
from datetime import timedelta

fake = Faker()

def generate_data(num_customers, output_dir):
    print(f"Generating SENIOR LEVEL data for {num_customers} customers...")
    
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # ---------------------------------------------------------
    # 1. CUSTOMERS (SCD2 Tracked)
    # ---------------------------------------------------------
    customer_ids = [fake.uuid4() for _ in range(num_customers)]
    
    customers_data = []
    for cid in customer_ids:
        customers_data.append({
            'customer_id': cid,
            'first_name': fake.first_name(),
            'last_name': fake.last_name(),
            'email': fake.email() if random.random() > 0.02 else None, # 2% null
            'country': random.choices(['US', 'GB', 'IN', 'FR', 'INVALID'], weights=[40, 20, 20, 15, 5])[0],
            'signup_date': fake.date_between(start_date='-3y', end_date='today'),
            'updated_at': fake.date_time_between(start_date='-1y', end_date='now')
        })
    df_customers = pd.DataFrame(customers_data)
    
    # ---------------------------------------------------------
    # 2. SUBSCRIPTIONS
    # ---------------------------------------------------------
    subs_data = []
    for cid in customer_ids:
        if random.random() < 0.85: # 85% have subs
            start_date = fake.date_between(start_date='-2y', end_date='today')
            status = random.choices(['Active', 'Cancelled', 'Upgraded'], weights=[60, 20, 20])[0]
            
            end_date = None
            if status in ['Cancelled', 'Upgraded']:
                end_date = start_date + timedelta(days=random.randint(30, 365))
                
            subs_data.append({
                'subscription_id': fake.uuid4(),
                'customer_id': cid,
                'plan_type': random.choice(['Basic', 'Standard', 'Premium']),
                'status': status,
                'start_date': start_date,
                'end_date': end_date
            })
    df_subs = pd.DataFrame(subs_data)

    # ---------------------------------------------------------
    # 3. PAYMENTS
    # ---------------------------------------------------------
    payments_data = []
    for _, sub in df_subs.iterrows():
        num_payments = random.randint(1, 12)
        base_amount = {'Basic': 999, 'Standard': 1499, 'Premium': 1999}[sub['plan_type']]
        
        for _ in range(num_payments):
            # Introduce varying currencies
            currency = random.choices(['USD', 'EUR', 'GBP'], weights=[70, 20, 10])[0]
            amount = base_amount if currency == 'USD' else int(base_amount * random.uniform(0.8, 1.2))
            
            # Inject Refunds (Negative)
            if random.random() < 0.05:
                amount = -amount
                
            payments_data.append({
                'transaction_id': fake.uuid4(),
                'subscription_id': sub['subscription_id'],
                'customer_id': sub['customer_id'] if random.random() > 0.05 else fake.uuid4(), # 5% Orphaned
                'amount': amount,
                'currency': currency,
                'payment_date': fake.date_time_between(start_date='-2y', end_date='now'),
            })
    df_payments = pd.DataFrame(payments_data)
    
    # Inject Duplicates
    df_payments = pd.concat([df_payments, df_payments.sample(frac=0.03)], ignore_index=True)

    # ---------------------------------------------------------
    # 4. CONTENT CONSUMPTION (High Volume, Semi-Structured, Skewed)
    # ---------------------------------------------------------
    events_data = []
    print("Generating high-volume content telemetry (this may take a moment)...")
    
    # Create a few "Mega-Users" (Bots) for Data Skew challenge
    mega_users = random.sample(customer_ids, max(1, int(num_customers * 0.01)))
    
    for cid in customer_ids:
        # Mega users generate 50x more events
        num_events = random.randint(50, 200) if cid in mega_users else random.randint(5, 30)
        
        base_time = fake.date_time_between(start_date='-30d', end_date='now')
        
        for i in range(num_events):
            # Simulate clustered sessions (events happening close together, then big gaps)
            if random.random() < 0.2:
                base_time += timedelta(hours=random.randint(1, 48)) # Gap -> New Session
            else:
                base_time += timedelta(minutes=random.randint(1, 15)) # Same session
                
            # INJECT BAD DATA: Late arriving data (timestamps recorded artificially in the past)
            event_time = base_time
            if random.random() < 0.02: # 2% of data arrives 4 days late
                event_time = base_time - timedelta(days=4)
                
            metadata = {
                "os": random.choice(['iOS', 'Android', 'Web', 'Roku']),
                "app_version": random.choice(['1.0', '1.1', '2.0']),
                "resolution": random.choice(['720p', '1080p', '4K']),
                # Random nested garbage to test JSON parsing
                "debug_info": {"battery": random.randint(10, 100)} if random.random() > 0.5 else None
            }
            
            events_data.append({
                'event_id': fake.uuid4(),
                'customer_id': cid,
                'event_timestamp': event_time,
                'event_type': random.choice(['play', 'pause', 'stop', 'buffer']),
                'device_metadata': json.dumps(metadata)
            })
            
    df_events = pd.DataFrame(events_data)
    df_events = df_events.sort_values('event_timestamp').reset_index(drop=True)

    # Save to CSV
    df_customers.to_csv(os.path.join(output_dir, 'customers.csv'), index=False)
    df_subs.to_csv(os.path.join(output_dir, 'subscriptions.csv'), index=False)
    df_payments.to_csv(os.path.join(output_dir, 'payments.csv'), index=False)
    df_events.to_csv(os.path.join(output_dir, 'content_consumption.csv'), index=False)
    
    print(f"Data generation complete! Files saved to '{output_dir}'.")
    print(f"Total Customers: {len(df_customers)}")
    print(f"Total Subscriptions: {len(df_subs)}")
    print(f"Total Payments: {len(df_payments)}")
    print(f"Total Events (Telemetry): {len(df_events)}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--env', type=str, choices=['dev', 'prod'], default='dev',
                        help="'dev' = lightweight testing, 'prod' = high volume testing.")
    parser.add_argument('--output', type=str, default='./raw_data')
    
    args = parser.parse_args()
    num_rows = 500 if args.env == 'dev' else 50000 
    # Note: 50,000 customers in prod will generate ~1 Million+ telemetry events!
    
    generate_data(num_rows, args.output)