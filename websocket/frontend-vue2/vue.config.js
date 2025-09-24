module.exports = {
  publicPath: "/",
  productionSourceMap: false,
  // devServer: { port: 8080 },
  devServer: {
    onBeforeSetupMiddleware: function (devServer) {
      devServer.app.use((req, res, next) => {
        console.log(`[${new Date().toISOString()}] ${req.method} ${req.url}`);
        next();
      });
    },
    host: "0.0.0.0",
    port: 8080
  }
};
