addEventListener('fetch', event => {
    event.respondWith(handleRequest(event.request))
  })
  
  async function handleRequest(request) {
    try {
      // URL of your EC2 instance
      const ec2Url = ''; // Your ec2 URL here
  
      const newRequest = new Request(ec2Url + new URL(request.url).pathname + new URL(request.url).search, {
        method: request.method,
        headers: new Headers({
          ...Object.fromEntries(request.headers),
          'Host': 'ec2.isitbadforme.tech',
          'X-Forwarded-For': request.headers.get('CF-Connecting-IP'),
          'X-Forwarded-Proto': 'https'
        }),
        body: request.body
      });
  
      console.log('New request:', newRequest);
  
      const response = await fetch(newRequest);
  
      console.log('Response status:', response.status);
      console.log('Response headers:', [...response.headers]);
  
      if (response.status === 101) {
        return response;
      }
  
      return response;
    } catch (error) {
      console.error('Error in worker script:', error);
      return new Response('Internal Server Error', { status: 500 });
    }
  }