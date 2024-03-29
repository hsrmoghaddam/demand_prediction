import pandas as pd
import numpy as np
from datetime import datetime
import geopy.distance
import matplotlib.pyplot as plt
import math
from xgboost import XGBRegressor
from sklearn.model_selection import cross_val_score
from sklearn.model_selection import RepeatedKFold
from numpy import absolute
from sklearn.metrics import mean_squared_error



# Importing customer data 
CUSTOMER_DATASET = 'DATA ADDRESS'
WEATHER_DATASET = 'DATA ADDRESS'

df = pd.read_csv(CUSTOMER_DATASET)
df_weather_data = pd.read_csv(WEATHER_DATASET)

# Getting dataframe head
print(df.head())
# Getting the dataframe shape
print(df.shape)
# Describing the dataframe
print(df.describe())
print(df.info())
# Counting the total of number of null elements
print(df.isnull().sum())
# Number of datapoint for different locations
print(df.groupby(['location_id'])['Id'].count())

# Converting the date to datatime object. 
df['reservation_start_time'] = pd.to_datetime(df['reservation_start_time'])
df['reservation_end_time'] = pd.to_datetime(df['reservation_end_time'])
df_weather_data['Date'] = pd.to_datetime(df_weather_data['Date'])

# Sort based on the reservation start time
df = df.sort_values('reservation_start_time')
df = df.reset_index()
# Getting only reservation start time date to extract weather  feature. 
df['start_date'] = pd.to_datetime(df['reservation_start_time']).dt.date
df_weather_data['Date'] = pd.to_datetime(df_weather_data['Date']).dt.date
# Making a list of start time unique dates
unique_dates = df['start_date'].unique()
# Making a list of locations
unique_locations = df['location_id'].unique()

# Extracting data for each city
df11 = df.loc[df['location_id'] == 11]
df13 = df.loc[df['location_id'] == 13]
df10 = df.loc[df['location_id'] == 10]


def create_dataset (df_reservation, df_weather):
    # This function gets reservation and weather data and creates a dataset that contains hourly demand, average trip distance, average travel time, average price, weather features, the hour of the day, and the day of the week.
    # Changing the reservation start times to its floor to help calculate hourly demand.
    df_reservation['reservation_start_time'] =  pd.to_datetime(df_reservation['reservation_start_time']).dt.floor(freq='H')
    
    # Make a new data frame and calculate the aggregate hourly demand
    df_reservation_new = pd.DataFrame(df_reservation.groupby(['reservation_start_time'])['Id'].count())
    # Calculate the average price of the rides per hour and add it to the data frame
    df_reservation_new['average_price'] = df_reservation.groupby(['reservation_start_time'])['net_price'].mean()
    # Calculating average hourly travel distances
    df_reservation_new['average_distance'] = df_reservation.groupby(['reservation_start_time'])['distance_meters'].mean()
    # Calculating average hourly travel times
    df_reservation_new['average_travel_time'] = df_reservation.groupby(['reservation_start_time'])['minutes_driven'].mean()
    
    df_reservation_new['start_date'] = df_reservation_new.index.date
    # Exreacting hour of the day
    df_reservation_new['hour_of_day'] = df_reservation_new.index.hour
    # Extracting day of the week
    df_reservation_new['day_of_week'] = df_reservation_new.index.dayofweek
    
    # Extracting weather data from the weather data set.
    descriptions = []
    max_temps = []
    heat_indexes = []
    wind_gust_speeds = []
    precipitations = []
    for date in unique_dates:
        weather_date_index = df_weather.index[df_weather['Date'] == date][0]
        description = df_weather.iloc[weather_date_index][1]
        max_temp = df_weather.iloc[weather_date_index][2]
        heat_index = df_weather.iloc[weather_date_index][3]
        wind_gust_speed = df_weather.iloc[weather_date_index][4]
        precipitation = df_weather.iloc[weather_date_index][5]
        # Adding all the extracted weather features to lists to be added to the data frame later.
        descriptions = descriptions + df_reservation_new['start_date'].value_counts()[date] * [description]
        max_temps = max_temps + df_reservation_new['start_date'].value_counts()[date] * [max_temp]
        heat_indexes = heat_indexes + df_reservation_new['start_date'].value_counts()[date] * [heat_index]
        wind_gust_speeds = wind_gust_speeds + df_reservation_new['start_date'].value_counts()[date] * [wind_gust_speed]
        precipitations = precipitations + df_reservation_new['start_date'].value_counts()[date] * [precipitation]
    
    # Adding the list of extracted  weather features to the data frame.
    df_reservation_new['description'] = descriptions
    df_reservation_new['max_temp'] = max_temps
    df_reservation_new['heat_index'] = heat_indexes
    df_reservation_new['wind_gust_speed'] = wind_gust_speeds
    df_reservation_new['precipitation'] = precipitations
    
    df_reservation_new.drop(columns = ['start_date'], inplace = True)
    df_reservation_new.rename(columns = {'Id' : 'demand'}, inplace = True)
    return df_reservation_new

def transform(df):
    # A function to transform variables
    # Transforming the hour of day to xhr and yhr to consider hours circularity
    df["xhr"] = df["hour_of_day"].apply(lambda x: math.sin(2*math.pi*x/24))
    
    df["yhr"] = df["hour_of_day"].apply(lambda x: math.cos(2*math.pi*x/24))
    
    df.drop(columns = ['hour_of_day'], inplace = True)
    
    # Transforming the day of the week and weather description to dummy variables
    df = pd.get_dummies(df, columns=["day_of_week", "description"], prefix=["day",""])
    return df


# Creating dataset using create_dataset function
df11_new = create_dataset(df,df_weather_data)
# Plotting hourly demand for the first day.
plt.figure(dpi = 300)
plt.plot(df11_new.iloc[:19, 0])
plt.xticks(rotation = 45) # Rotates X-Axis Ticks by 45-degrees
plt.ylabel('Demand')
plt.show()
# Transform dataset by using transform function
df11_new = transform(df11_new)

# Split data into input and output columns
X, y = df11_new.iloc[:, 1:], df11_new.iloc[:, 0]

# define model
model = XGBRegressor()

# define model evaluation method
cv = RepeatedKFold(n_splits=10, n_repeats=3, random_state=1)

# evaluate model
scores = cross_val_score(model, X, y, scoring='neg_mean_squared_error', cv=cv, n_jobs=-1)

# force scores to be positive
scores = absolute(scores)
print('---------- Mean MSE: %.3f (%.3f) ----------' % (scores.mean(), scores.std()) )


# Also it is possible to look at the problem like a time series analysis
# So first it is required to fill the time gaps in the data
df11_ts = create_dataset(df11, df_weather_data)

time_range = pd.date_range(start=df11_ts.index.min(), end=df11_ts.index.max(), freq='1h')
time_range.freq = None
missing_intervals = time_range[~time_range.isin(df11_ts.index)]

df11_ts = df11_ts.reindex(time_range)

# Extracting hour of day and day of week for all data points including missing ones
df11_ts['hour_of_day'] = df11_ts.index.hour
df11_ts['day_of_week'] = df11_ts.index.dayofweek
# Fill missing demand values using forward fill
df11_ts= df11_ts.ffill()

# Transform dataset by using transform function
df11_ts = transform(df11_ts)
df11_ts['demand_previous_day'] = df11_ts['demand'].shift(24)
df11_ts['demand_two_days_before'] = df11_ts['demand'].shift(48)
df11_ts['demand_three_days_before'] = df11_ts['demand'].shift(72)

# Remove rows with missing data in the new columns
df11_ts.dropna(subset=['demand_previous_day', 'demand_two_days_before', 'demand_three_days_before'], inplace=True)

X_ts, y_ts = df11_ts.iloc[:, 1:], df11_ts.iloc[:, 0]

# Split the data into training and testing sets
train_size = int(len(X_ts) * 0.8)
X_train, X_test = X_ts[:train_size], X_ts[train_size:]
y_train, y_test = y_ts[:train_size], y_ts[train_size:]

# Create and train the XGBoost regressor
model_ts = XGBRegressor()
model_ts.fit(X_train, y_train)

# Make predictions on the test set
y_pred = model_ts.predict(X_test)

# Calculate root mean squared error (RMSE)
rmse = mean_squared_error(y_test, y_pred)
print(('---------- MSE ts: %.3f ----------' % (rmse )))

# Evaluating feature's importance
feature_importance = model_ts.feature_importances_
sorted_idx = np.argsort(feature_importance)
pos = np.arange(sorted_idx.shape[0]) + 10
fig = plt.figure(figsize=(12, 12))
plt.subplot(1, 2, 1)
plt.barh(pos, feature_importance[sorted_idx], align="center")
plt.yticks(pos, df11_ts.columns[1:][sorted_idx], fontsize=8)
plt.title("Feature Importance")


# In the next step one could find geographic service areas and divide them into smaller areas using grids. These grids could be used to assign trips that fall between grids to clusters. These clusters could be used to predict demand in smaller areas and also it is possible to extract more features to train models.
# Finding the extreme coordinates to find the coverage area dimensions
min_start_longitude_11 =  df11['start_longitude'].min()
max_start_longitude_11 =  df11['start_longitude'].max()
min_start_latitude_11 =  df11['start_latitude'].min()
max_start_latitude_11 =  df11['start_latitude'].max()

min_end_longitude_11 =  df11['end_longitude'].min()
max_end_longitude_11 =  df11['end_longitude'].max()
min_end_latitude_11 =  df11['end_latitude'].min()
max_end_latitude_11 =  df11['end_latitude'].max()

min_long_11 = min (min_start_longitude_11, min_end_longitude_11)
max_long_11 = max (max_start_longitude_11, max_end_longitude_11)
min_lat_11 = min (min_start_latitude_11, min_end_latitude_11)
max_lat_11 = max (max_start_latitude_11, max_end_latitude_11)

area_length_11 = geopy.distance.geodesic((min_lat_11,min_long_11 ), (min_lat_11,max_long_11)).km
area_width_11 = geopy.distance.geodesic((max_lat_11,min_long_11 ), (min_lat_11,min_long_11)).km


min_start_longitude_13 =  df13['start_longitude'].min()
max_start_longitude_13 =  df13['start_longitude'].max()
min_start_latitude_13 =  df13['start_latitude'].min()
max_start_latitude_13 =  df13['start_latitude'].max()

min_end_longitude_13 =  df13['end_longitude'].min()
max_end_longitude_13 =  df13['end_longitude'].max()
min_end_latitude_13 =  df13['end_latitude'].min()
max_end_latitude_13 =  df13['end_latitude'].max()

min_long_13 = min (min_start_longitude_13, min_end_longitude_13)
max_long_13 = max (max_start_longitude_13, max_end_longitude_13)
min_lat_13 = min (min_start_latitude_13, min_end_latitude_13)
max_lat_13 = max (max_start_latitude_13, max_end_latitude_13)

area_length_13 = geopy.distance.geodesic((min_lat_13,min_long_13 ), (min_lat_13,max_long_13)).km
area_width_13 = geopy.distance.geodesic((max_lat_13,min_long_13 ), (min_lat_13,min_long_13)).km


min_start_longitude_10 =  df10['start_longitude'].min()
max_start_longitude_10 =  df10['start_longitude'].max()
min_start_latitude_10 =  df10['start_latitude'].min()
max_start_latitude_10 =  df10['start_latitude'].max()

min_end_longitude_10 =  df10['end_longitude'].min()
max_end_longitude_10 =  df10['end_longitude'].max()
min_end_latitude_10 =  df10['end_latitude'].min()
max_end_latitude_10 =  df10['end_latitude'].max()

min_long_10 = min (min_start_longitude_10, min_end_longitude_10)
max_long_10 = max (max_start_longitude_10, max_end_longitude_10)
min_lat_10 = min (min_start_latitude_10, min_end_latitude_10)
max_lat_10 = max (max_start_latitude_10, max_end_latitude_10)

area_length_10 = geopy.distance.geodesic((min_lat_10,min_long_10 ), (min_lat_10,max_long_10)).km
area_width_10 = geopy.distance.geodesic((max_lat_10,min_long_10 ), (min_lat_10,min_long_10)).km

# Generating the grid lines for clustering. Here I want to have a 5*5 grid. 
grids_long_11 = np.linspace(min_long_11, max_long_11, num=5+1)
grids_lat_11 = np.linspace(min_lat_11, max_lat_11, num=5+1)

# Here I am using 5 to 5 grids and making an array with this shape for cluster names. 
cluster_ids = np.arange(1,26).reshape(5,5)

# Make a list to add trip cluster ids to it.
origin_cluster_ids = []
destination_cluster_ids = []

# Assigning trips' origin and destination to corresponding clusters
df_11_dict = df11.to_dict('records')
for k in range (len(df_11_dict)):
    origin_lat = df_11_dict[k]['start_latitude']
    origin_long = df_11_dict[k]['start_longitude']
    destination_lat = df_11_dict[k]['end_latitude']
    destination_long = df_11_dict[k]['end_longitude']
    if origin_long <= grids_long_11[1]:
        cluster_i = 0
    if grids_long_11[1] < origin_long <= grids_long_11[2]:
        cluster_i = 1
    if grids_long_11[2] < origin_long <= grids_long_11[3]:
        cluster_i = 2
    if grids_long_11[3] < origin_long <= grids_long_11[4]:
        cluster_i = 3
    if grids_long_11[4] < origin_long <= grids_long_11[5]:
        cluster_i = 4

    if origin_lat <= grids_lat_11[1]:
        cluster_j = 0
    if grids_lat_11[1] < origin_lat <= grids_lat_11[2]:
        cluster_j = 1
    if grids_lat_11[2] < origin_lat <= grids_lat_11[3]:
        cluster_j = 2
    if grids_lat_11[3] < origin_lat <= grids_lat_11[4]:
        cluster_j = 3
    if grids_lat_11[4] < origin_lat <= grids_lat_11[5]:
        cluster_j = 4
    origin_cluster_id = cluster_ids[cluster_i][cluster_j]
    origin_cluster_ids.append(origin_cluster_id)
    
    if destination_long <= grids_long_11[1]:
        cluster_i = 0
    if grids_long_11[1] < destination_long <= grids_long_11[2]:
        cluster_i = 1
    if grids_long_11[2] < destination_long <= grids_long_11[3]:
        cluster_i = 2
    if grids_long_11[3] < destination_long <= grids_long_11[4]:
        cluster_i = 3
    if grids_long_11[4] < destination_long <= grids_long_11[5]:
        cluster_i = 4

    if destination_lat <= grids_lat_11[1]:
        cluster_j = 0
    if grids_lat_11[1] < destination_lat <= grids_lat_11[2]:
        cluster_j = 1
    if grids_lat_11[2] < destination_lat <= grids_lat_11[3]:
        cluster_j = 2
    if grids_lat_11[3] < destination_lat <= grids_lat_11[4]:
        cluster_j = 3
    if grids_lat_11[4] < destination_lat <= grids_lat_11[5]:
        cluster_j = 4
    destination_cluster_id = cluster_ids[cluster_i][cluster_j]
    destination_cluster_ids.append(destination_cluster_id)

df11['origin_cluster'] = origin_cluster_ids
df11['destination_cluster'] = destination_cluster_ids
