from django.shortcuts import redirect, render

def home(request):
    return redirect('entries:home')