import logging

from django.contrib import messages
from django.contrib.auth import get_user_model, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.views import LoginView
from django.shortcuts import redirect, render, get_object_or_404

from .forms import CustomPasswordChangeForm, UserCreationForm, UserProfileForm, UserEditForm

logger = logging.getLogger(__name__)

User = get_user_model()


class DaybookLoginView(LoginView):
    template_name = 'accounts/login.html'

    def form_invalid(self, form):
        username = (self.request.POST.get('username') or '').strip()
        inactive_user = User.objects.filter(username=username, is_active=False).first()

        if inactive_user:
            messages.error(self.request, 'User is inactive. Contact administrator.')
        else:
            messages.error(self.request, 'Invalid username or password. Please try again.')

        return super().form_invalid(form)


def is_admin(user):
    return user.is_superuser or user.groups.filter(name='Admin').exists()


def can_toggle_user_active_status(actor, target_user):
    target_is_admin = target_user.groups.filter(name='Admin').exists()
    target_is_staff = target_user.groups.filter(name='Staff').exists()

    # Super admin can manage both Admin and Staff group users
    if actor.is_superuser:
        return target_is_admin or target_is_staff

    # Admin group users can manage only Staff group users (not Admin users)
    return actor.groups.filter(name='Admin').exists() and target_is_staff and not target_is_admin


def can_edit_user(actor, target_user):
    """
    Check if actor can edit target_user's information.
    - Super admin can edit Admin and Staff group users
    - Admin group users can edit Staff group users only
    """
    # Prevent editing self via this function (use profile edit instead)
    if actor.username == target_user.username:
        return False
    
    target_is_admin = target_user.groups.filter(name='Admin').exists()
    target_is_staff = target_user.groups.filter(name='Staff').exists()

    # Super admin can edit both Admin and Staff group users
    if actor.is_superuser:
        return target_is_admin or target_is_staff

    # Admin group users can edit only Staff group users (not Admin users)
    return actor.groups.filter(name='Admin').exists() and target_is_staff and not target_is_admin


def logout_view(request):
    username = request.user.username if request.user.is_authenticated else 'Unknown'
    logout(request)
    logger.info(f"User logged out: {username}")
    return redirect('entries:home')


@login_required
def user_settings(request):
    context = {
        'nav_title': 'Users',
    }
    return render(request, 'accounts/user_settings.html', context)


@login_required
def edit_profile(request):
    if request.method == 'POST':
        form = UserProfileForm(request.POST, instance=request.user)
        if form.is_valid():
            try:
                changed_fields = [field for field in form.changed_data]
                form.save()
                logger.info(f"Profile updated by {request.user.username}, fields changed: {', '.join(changed_fields) if changed_fields else 'None'}")
                messages.success(request, 'Profile updated successfully!')
                return redirect('accounts:user_settings')
            except Exception as e:
                logger.error(f"Error updating profile for {request.user.username}: {str(e)}", exc_info=True)
                messages.error(request, 'An error occurred while updating profile.')
    else:
        form = UserProfileForm(instance=request.user)
    
    context = {
        'nav_title': 'Users',
        'form': form,
    }
    return render(request, 'accounts/edit_profile.html', context)


@login_required
def change_password(request):
    if request.method == 'POST':
        form = CustomPasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            try:
                user = form.save()
                update_session_auth_hash(request, user)
                logger.info(f"Password changed successfully for user: {request.user.username}")
                messages.success(request, 'Password changed successfully!')
                return redirect('accounts:user_settings')
            except Exception as e:
                logger.error(f"Error changing password for {request.user.username}: {str(e)}", exc_info=True)
                messages.error(request, 'An error occurred while changing password.')
    else:
        form = CustomPasswordChangeForm(request.user)
    
    context = {
        'nav_title': 'Users',
        'form': form,
    }
    return render(request, 'accounts/change_password.html', context)


@login_required
@user_passes_test(is_admin, login_url='/accounts/login/')
def create_user(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            try:
                new_user = form.save()
                user_groups = ', '.join([g.name for g in new_user.groups.all()]) if new_user.groups.exists() else 'None'
                logger.info(f"User created by {request.user.username}: new username={new_user.username}, groups={user_groups}")
                messages.success(request, 'User created successfully!')
                return redirect('accounts:users_list')
            except Exception as e:
                logger.error(f"Error creating user by {request.user.username}: {str(e)}", exc_info=True)
                messages.error(request, 'An error occurred while creating user.')
    else:
        form = UserCreationForm()
    
    context = {
        'nav_title': 'Users',
        'form': form,
    }
    return render(request, 'accounts/create_user.html', context)


@login_required
@user_passes_test(is_admin, login_url='/accounts/login/')
def users_list(request):
    users = User.objects.all().select_related().prefetch_related('groups')
    context = {
        'nav_title': 'Users',
        'users': users,
    }
    return render(request, 'accounts/users_list.html', context)

@login_required
@user_passes_test(is_admin, login_url='/accounts/login/')
def user_info(request,username):
    selected_user = get_object_or_404(User,username=username)
    is_staff_member = selected_user.groups.filter(name='Staff').exists()
    can_manage_active_status = can_toggle_user_active_status(request.user, selected_user)
    can_make_inactive = can_manage_active_status and selected_user.is_active
    can_make_active = can_manage_active_status and not selected_user.is_active
    can_edit = can_edit_user(request.user, selected_user)
    context={
        "nav_title": "Users",
        "selected_user": selected_user,
        "is_staff_member": is_staff_member,
        "can_make_inactive": can_make_inactive,
        "can_make_active": can_make_active,
        "can_edit": can_edit,
    }
    return render(request, 'accounts/user_info.html', context)


@login_required
@user_passes_test(is_admin, login_url='/accounts/login/')
def edit_user(request, username):
    selected_user = get_object_or_404(User, username=username)
    
    # Check if actor has permission to edit this user
    if not can_edit_user(request.user, selected_user):
        messages.error(request, 'You do not have permission to edit this user.')
        return redirect('accounts:user_info', username=username)
    
    if request.method == 'POST':
        form = UserEditForm(request.POST, instance=selected_user)
        if form.is_valid():
            try:
                changed_fields = [field for field in form.changed_data]
                form.save()
                logger.info(f"User {selected_user.username} edited by {request.user.username}, fields changed: {', '.join(changed_fields) if changed_fields else 'None'}")
                messages.success(request, f'User {selected_user.username} updated successfully!')
                return redirect('accounts:user_info', username=username)
            except Exception as e:
                logger.error(f"Error updating user {selected_user.username} by {request.user.username}: {str(e)}", exc_info=True)
                messages.error(request, 'An error occurred while updating user.')
    else:
        form = UserEditForm(instance=selected_user)
    
    context = {
        'nav_title': 'Users',
        'form': form,
        'selected_user': selected_user,
    }
    return render(request, 'accounts/edit_user.html', context)

@login_required
@user_passes_test(is_admin, login_url='/accounts/login/')
def promote_to_admin(request, username):
    if request.method == 'POST':
        try:
            selected_user = get_object_or_404(User, username=username)
            
            # Get the groups
            from django.contrib.auth.models import Group
            staff_group = Group.objects.get(name='Staff')
            admin_group = Group.objects.get(name='Admin')
            
            # Remove from Staff and add to Admin
            selected_user.groups.remove(staff_group)
            selected_user.groups.add(admin_group)
            
            logger.warning(f"User promoted to Admin by {request.user.username}: {selected_user.username}")
            messages.success(request, f'{selected_user.username} has been promoted to Admin group.')
            return redirect('accounts:user_info', username=username)
        except Exception as e:
            logger.error(f"Error promoting user {username} to Admin by {request.user.username}: {str(e)}", exc_info=True)
            messages.error(request, 'An error occurred while promoting user.')
            return redirect('accounts:user_info', username=username)
    
    return redirect('accounts:user_info', username=username)


@login_required
@user_passes_test(is_admin, login_url='/accounts/login/')
def deactivate_staff_user(request, username):
    if request.method == 'POST':
        try:
            selected_user = get_object_or_404(User, username=username)

            if not can_toggle_user_active_status(request.user, selected_user):
                messages.error(request, f'You do not have permission to change active status for {selected_user.username}.')
                return redirect('accounts:user_info', username=username)

            if not selected_user.is_active:
                messages.info(request, f'{selected_user.username} is already inactive.')
                return redirect('accounts:user_info', username=username)

            selected_user.is_active = False
            selected_user.save(update_fields=['is_active'])

            logger.warning(f"User deactivated by {request.user.username}: {selected_user.username}")
            messages.success(request, f'{selected_user.username} has been marked as inactive.')
            return redirect('accounts:user_info', username=username)
        except Exception as e:
            logger.error(f"Error deactivating user {username} by {request.user.username}: {str(e)}", exc_info=True)
            messages.error(request, 'An error occurred while deactivating the user.')
            return redirect('accounts:user_info', username=username)

    return redirect('accounts:user_info', username=username)


@login_required
@user_passes_test(is_admin, login_url='/accounts/login/')
def activate_staff_user(request, username):
    if request.method == 'POST':
        try:
            selected_user = get_object_or_404(User, username=username)

            if not can_toggle_user_active_status(request.user, selected_user):
                messages.error(request, f'You do not have permission to change active status for {selected_user.username}.')
                return redirect('accounts:user_info', username=username)

            if selected_user.is_active:
                messages.info(request, f'{selected_user.username} is already active.')
                return redirect('accounts:user_info', username=username)

            selected_user.is_active = True
            selected_user.save(update_fields=['is_active'])

            logger.warning(f"User activated by {request.user.username}: {selected_user.username}")
            messages.success(request, f'{selected_user.username} has been marked as active.')
            return redirect('accounts:user_info', username=username)
        except Exception as e:
            logger.error(f"Error activating user {username} by {request.user.username}: {str(e)}", exc_info=True)
            messages.error(request, 'An error occurred while activating the user.')
            return redirect('accounts:user_info', username=username)

    return redirect('accounts:user_info', username=username)
