ckan.module('reject_confirm', function ($, _) {
  return {
    initialize: function () {
      $.proxyAll(this, /_on/);
      $('.reject_confirm_handle').click(function(e) {
          e.preventDefault();
          $('#reject_confirm').trigger('click');
      });
    }
  };
});
