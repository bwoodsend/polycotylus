#FROM alpine

#RUN apk add doas shadow sudo

#RUN useradd --create-home --non-unique --uid 1000 --groups wheel user
#RUN mkdir -p 
#RUN mkdir /io && chown user /io

FROM alpine:latest

# Install doas
RUN apk add doas

# Add a user to the wheel group
RUN adduser -D myuser && adduser myuser wheel

# Set up doas configuration
RUN echo 'permit persist :wheel' > /etc/doas.d/doas.conf
RUN echo 'permit nopass :wheel' > /etc/doas.d/doas.conf

