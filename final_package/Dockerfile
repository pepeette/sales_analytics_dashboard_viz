FROM python:3.9

# Set the working directory in the container
WORKDIR /dashboard

# Copy the local code to the container
COPY . .

# Install any additional dependencies here
RUN pip install --no-cache-dir -r requirements.txt

# Copy the additional files to the container
COPY current.csv currentsql.csv pastfour.csv credentials.py logo.png ./

# Start the Python script server and expose port 8090
CMD ["python", "ezidb.py", "--port=8080", "--no-browser"]
EXPOSE 8080
